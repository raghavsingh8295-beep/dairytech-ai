# Book drop-in location

Put the source PDFs for the AI Dairy Assistant here (this directory is
gitignored — the PDFs are likely copyrighted and never committed).

Then ingest each one:

```bash
pip install -r requirements-ingest.txt   # once, adds PyMuPDF for extraction
python scripts/ingest_book.py --title "栄養バランスの再点検 — 炭水化物とタンパク質を使いこなす" data/books/book1.pdf
python scripts/ingest_book.py --title "今日も明日も 牛群検定が約束するあなたの酪農経営！" data/books/book2.pdf
```

Use the exact title you want to appear in the app's citations — it's
stored once and re-ingesting the same file (unchanged) is a no-op.

Point your local `.env`'s `DATABASE_URL` at the same Postgres/Neon
database the deployed API uses before running this, so the ingested book
is actually visible to the live app — the SQLite fallback has no pgvector
support and can't run this feature at all.
