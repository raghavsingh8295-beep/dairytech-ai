"""Regression tests use only an isolated in-memory database."""
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['JWT_SECRET_KEY'] = 'isolated-test-key-not-used-by-the-application'

import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from api.security import _decode_token, create_access_token
from config.settings import settings
from controllers.auth_controller import AuthenticatedUser
from database.base import Base
from models.user import User, UserRole
from utils.exceptions import AppError
from utils.parsing import parse_optional_float
from utils.validators import validate_non_negative


class NumericTests(unittest.TestCase):
    def test_reject_nonfinite_form_values(self):
        for raw in ('nan', 'NaN', 'inf', '-inf', '1e999'):
            with self.subTest(raw=raw), self.assertRaises(AppError):
                parse_optional_float(raw, 'Milk')

    def test_normal_and_blank_form_values(self):
        self.assertIsNone(parse_optional_float(' ', 'Milk'))
        self.assertEqual(parse_optional_float(' 12.5 ', 'Milk'), 12.5)
        self.assertEqual(parse_optional_float('0', 'Milk'), 0)

    def test_nonnegative_values_must_be_finite(self):
        for value in (float('inf'), float('-inf'), float('nan'), -1):
            self.assertFalse(validate_non_negative(value))
        for value in (0, 2.5):
            self.assertTrue(validate_non_negative(value))


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.user = User(username='testuser', email='test@example.com', full_name='Test',
                         password_hash='unused', security_question='unused',
                         security_answer_hash='unused', role=UserRole.ADMIN, is_active=True)
        self.session.add(self.user)
        self.session.commit()
        self.token = create_access_token(AuthenticatedUser(self.user.id, 'testuser', 'Test',
                                          'test@example.com', UserRole.ADMIN, True))
        @contextmanager
        def isolated_session():
            yield self.session
        self.patcher = patch('api.security.get_db_session', isolated_session)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.session.close()
        self.engine.dispose()

    def test_current_role_replaces_stale_token_role(self):
        self.user.role = UserRole.EMPLOYEE
        self.session.commit()
        self.assertEqual(_decode_token(self.token).role, UserRole.EMPLOYEE)

    def test_deactivated_account_rejected(self):
        self.user.is_active = False
        self.session.commit()
        with self.assertRaises(HTTPException) as error:
            _decode_token(self.token)
        self.assertEqual(error.exception.status_code, 401)

    def test_deleted_account_rejected(self):
        self.session.delete(self.user)
        self.session.commit()
        with self.assertRaises(HTTPException) as error:
            _decode_token(self.token)
        self.assertEqual(error.exception.status_code, 401)

    def test_active_account_accepted(self):
        self.assertEqual(_decode_token(self.token).id, self.user.id)

    def test_invalid_missing_and_expired_claims_rejected(self):
        now = datetime.now(timezone.utc)
        for payload in ({'sub': 'bad', 'iat': now, 'exp': now + timedelta(days=1)},
                        {'sub': str(self.user.id), 'iat': now},
                        {'sub': str(self.user.id), 'iat': now-timedelta(days=2), 'exp': now-timedelta(days=1)}):
            token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
            with self.subTest(payload=payload), self.assertRaises(HTTPException) as error:
                _decode_token(token)
            self.assertEqual(error.exception.status_code, 401)


class DailyRecordUpdateTests(unittest.TestCase):
    def setUp(self):
        from models.farm import Farm
        from models.cow import Cow, CowGender
        from controllers.daily_record_controller import DailyRecordController
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        user = User(username='owner', email='owner@example.com', full_name='Owner',
                    password_hash='unused', security_question='unused', security_answer_hash='unused',
                    role=UserRole.FARM_OWNER, is_active=True)
        self.session.add(user); self.session.flush()
        farm = Farm(name='Test farm', owner_id=user.id)
        self.session.add(farm); self.session.flush()
        cow = Cow(farm_id=farm.id, tag_number='T1', qr_code_value='T1', breed='Test', gender=CowGender.FEMALE)
        self.session.add(cow); self.session.commit()
        self.actor = AuthenticatedUser(user.id, user.username, user.full_name, user.email, user.role, True)
        self.cow_id = cow.id
        self.controller = DailyRecordController()
        @contextmanager
        def isolated_session():
            try:
                yield self.session
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
        self.patcher = patch('controllers.daily_record_controller.get_db_session', isolated_session)
        self.patcher.start()
        from datetime import date
        self.day = date(2026, 9, 9)
        self.record = self.controller.save_record(self.actor, cow_id=cow.id, record_date=self.day,
                          milk_morning_liters=10, medicine_given='Recorded treatment', feed_intake_kg=15)

    def tearDown(self):
        self.patcher.stop(); self.session.close(); self.engine.dispose()

    def test_api_omitted_fields_preserved_and_explicit_null_clears(self):
        from api.routers.daily_records import save_record_for_cow
        from api.schemas import DailyRecordCreateIn
        saved = save_record_for_cow(self.cow_id, DailyRecordCreateIn(record_date=self.day, milk_evening_liters=8), self.actor)
        self.assertEqual(saved.medicine_given, 'Recorded treatment')
        self.assertEqual(saved.feed_intake_kg, 15)
        self.assertEqual(saved.milk_morning_liters, 10)
        cleared = save_record_for_cow(self.cow_id, DailyRecordCreateIn(record_date=self.day, medicine_given=None), self.actor)
        self.assertIsNone(cleared.medicine_given)
        self.assertEqual(cleared.milk_evening_liters, 8)

    def test_stale_api_update_returns_conflict(self):
        from api.routers.daily_records import save_record_for_cow
        from api.schemas import DailyRecordCreateIn
        payload = DailyRecordCreateIn(record_date=self.day, expected_updated_at=None, milk_morning_liters=99)
        with self.assertRaises(HTTPException) as error:
            save_record_for_cow(self.cow_id, payload, self.actor)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.controller.get_for_date(self.actor, self.cow_id, self.day).milk_morning_liters, 10)

    def test_matching_version_saves(self):
        from api.routers.daily_records import save_record_for_cow
        from api.schemas import DailyRecordCreateIn
        saved = save_record_for_cow(self.cow_id, DailyRecordCreateIn(record_date=self.day,
                    expected_updated_at=self.record.updated_at, milk_evening_liters=7), self.actor)
        self.assertEqual(saved.milk_evening_liters, 7)
        self.assertEqual(saved.medicine_given, 'Recorded treatment')

    def test_confirmed_record_stays_locked(self):
        self.controller.confirm_record(self.actor, self.record.id)
        from controllers.daily_record_controller import DailyRecordError
        with self.assertRaises(DailyRecordError):
            self.controller.save_record(self.actor, cow_id=self.cow_id, record_date=self.day, milk_morning_liters=20)

    def test_api_rejects_nonfinite_numbers(self):
        from api.schemas import DailyRecordCreateIn
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            DailyRecordCreateIn(record_date=self.day, milk_morning_liters=float('inf'))

if __name__ == '__main__':
    unittest.main()
