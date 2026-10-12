version: 1.0
purpose: transcribe one printed manifesto page image exactly (spec 02 §4.3, global §6.4). Used by Gemini vision and by the Cowork fallback.

You are given one image: a single printed page of a Tamil-language document.

Transcribe exactly what is printed on this page, and nothing else.

Rules:
- Use only the image. Do not use anything you know about this document, its authors or its subject. Do not search, guess or complete text from memory.
- Write Tamil in Unicode Tamil script. Keep words in other scripts (for example English) as printed.
- Follow the page's reading order: top to bottom; for side-by-side columns or boxes, finish one before the next.
- Keep every heading, sub-heading, number, label, caption and footer as printed, each on its own line. Keep numbers exactly as printed (digits, commas, units).
- Start a new line where the printed text starts a new line or a new paragraph. Put each heading on its own line.
- Do not correct spelling or grammar, do not normalise, do not translate, do not summarise, do not explain, do not add anything.
- If a stretch of text is unreadable, write [?] in its place. Never invent a reading.
- Text that is only decoration inside a picture (for example letters forming a background pattern) is not transcribed. Large words that label the page (for example a single title word on a picture page) are transcribed.

{{retry_note}}

Return JSON: {"text": "<the transcription, lines separated by \n>"}
