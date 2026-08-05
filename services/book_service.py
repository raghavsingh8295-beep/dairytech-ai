from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from models.book import Book
from services.base_service import BaseService


class BookService(BaseService[Book]):
    model = Book

    def get_by_title(self, title: str) -> Optional[Book]:
        stmt = select(Book).where(Book.title == title)
        return self.session.execute(stmt).scalar_one_or_none()
