# Third-party notices

The project's own code is licensed under the GNU General Public License v3 or later (`LICENSE`, D-043).
It includes the following third-party code.

## Open-Tamil `txt2unicode` — VANAVIL → Unicode table

- **Vendored file:** `src/ept/extract/vanavil_map.py`
- **What:** the `vanavil2utf8` mapping table (unchanged) and the `encode2unicode` / `vanavil2unicode` functions (reduced to the Python 3 `str` case), used to convert Tamil typed in VANAVIL-family legacy fonts to Unicode (spec 02 §4.2, D-035).
- **Author:** Arulalan T. <arulalant@gmail.com>, © 2014; part of open-tamil / txt2uni.
- **Source:** Open-Tamil 1.1, PyPI sdist `Open-Tamil-1.1.tar.gz` (sha256 `339623ef6aefbca8e6d8fff3e2901d437f5d9b774576f1eb6c1540fbbe20ebb8`), files `tamil/txt2unicode/encode2utf8.py` and `tamil/txt2unicode/encode2unicode.py`. Project: https://github.com/Ezhil-Language-Foundation/open-tamil
- **Licence:** GNU General Public License v3 or (at your option) any later version. The original copyright and licence header is kept at the top of the vendored file.
- **Why vendored:** `pip install open-tamil` fails on current Python, and only the table is needed.

## BAAI `bge-small-en-v1.5` — embedding model (used, not vendored)

- **What:** the sentence-embedding model used for dense evidence retrieval (spec 04 §4.5, D-079). It is downloaded from Hugging Face at first use and is not part of this repository; derived vectors live in `data/processed/embeddings/` (not committed).
- **Source:** https://huggingface.co/BAAI/bge-small-en-v1.5, revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` (pinned in `config/settings.yaml`, `retrieve.dense.revision`).
- **Authors:** Beijing Academy of Artificial Intelligence (BAAI), FlagEmbedding project. Paper: Xiao et al., "C-Pack: Packaged Resources To Advance General Chinese Embedding" (2023), arXiv:2309.07597.
- **Licence:** MIT.
