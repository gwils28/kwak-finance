# Import fixtures

Every file here is **synthetic**: it copies a bank export's exact layout (header lines,
separators, encoding, line endings, number and date formats, label shapes) with invented
account numbers, dates, amounts, merchants, names and references. Never commit a real export.

To add a format: inspect the real file's structure with its letters and digits masked, write a
synthetic file in the same layout, then a failing test in `backend/tests/core/imports/`.

| File | Layout |
|---|---|
| `societe_generale/checking.csv` | SG checking: summary line with balance, 5 columns, ISO-8859-1, CRLF |
| `societe_generale/savings.csv` | SG savings (Livret A, LDDS): snake_case header, trailing `;`, ISO-8859-1, CRLF |
