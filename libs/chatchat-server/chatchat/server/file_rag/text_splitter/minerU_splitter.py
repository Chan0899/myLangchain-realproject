import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain.docstore.document import Document
from langchain.text_splitter import CharacterTextSplitter

from chatchat.server.utils import get_Embeddings, get_default_embedding
from chatchat.utils import build_logger


logger = build_logger()


def _import_pdfplumber():
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError(
            "Could not import pdfplumber. Please install pdfplumber before using this PDF semantic splitter."
        ) from exc

    return pdfplumber


def _import_semantic_chunker():
    try:
        from langchain_experimental.text_splitter import SemanticChunker
    except ImportError as exc:
        raise ImportError(
            "Could not import SemanticChunker. Please install langchain-experimental before using MinerUSplitter."
        ) from exc

    return SemanticChunker


def _normalize_text(content: str) -> str:
    lines = [line.strip() for line in content.splitlines()]
    normalized_lines: List[str] = []
    previous_blank = False
    for line in lines:
        is_blank = not line
        if is_blank and previous_blank:
            continue
        normalized_lines.append(line)
        previous_blank = is_blank
    return "\n".join(normalized_lines).strip()


def _table_to_text(table: List[List[Optional[str]]]) -> str:
    rows: List[str] = []
    for row in table:
        if not row:
            continue
        cells = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


class MinerUSplitter(CharacterTextSplitter):
    def __init__(
        self,
        pdf: bool = True,
        embed_model: Optional[str] = None,
        breakpoint_threshold_type: str = "percentile",
        breakpoint_threshold_amount: float = 95.0,
        min_chunk_size: int = 200,
        mineru_output_root: Optional[str] = None,
        **kwargs: Any,
    ):
        chunk_size = kwargs.get("chunk_size", 1500)
        kwargs.setdefault("separator", "\n\n")
        super().__init__(**kwargs)
        self.pdf = pdf
        self.embed_model = embed_model or get_default_embedding()
        self.breakpoint_threshold_type = breakpoint_threshold_type
        self.breakpoint_threshold_amount = breakpoint_threshold_amount
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = chunk_size
        self.mineru_output_root = mineru_output_root
        self._semantic_splitter = None

    def _get_semantic_splitter(self):
        if self._semantic_splitter is None:
            SemanticChunker = _import_semantic_chunker()
            embeddings = get_Embeddings(embed_model=self.embed_model)
            self._semantic_splitter = SemanticChunker(
                embeddings=embeddings,
                breakpoint_threshold_type=self.breakpoint_threshold_type,
                breakpoint_threshold_amount=self.breakpoint_threshold_amount,
                min_chunk_size=self.min_chunk_size,
            )
        return self._semantic_splitter

    def _parse_pdf_with_pdfplumber(self, pdf_path: str, metadata: Optional[Dict] = None) -> Document:
        pdfplumber = _import_pdfplumber()
        page_texts: List[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_parts: List[str] = []
                extracted_text = page.extract_text()
                if extracted_text:
                    page_parts.append(extracted_text)

                for table in page.extract_tables() or []:
                    table_text = _table_to_text(table)
                    if table_text:
                        page_parts.append(table_text)

                if page_parts:
                    page_texts.append("\n".join(page_parts))

        extracted_content = _normalize_text("\n\n".join(page_texts))
        if not extracted_content:
            raise ValueError(f"No text extracted from PDF: {pdf_path}")

        merged_metadata = dict(metadata or {})
        merged_metadata["source"] = pdf_path
        merged_metadata["pdf_parser"] = "pdfplumber"
        return Document(
            page_content=extracted_content,
            metadata=merged_metadata,
        )

    def _preprocess_document(self, doc: Document) -> Document:
        source = str(doc.metadata.get("source", ""))
        if not source:
            return doc

        suffix = Path(source).suffix.lower()
        if not self.pdf or suffix != ".pdf":
            return doc

        if not os.path.isfile(source):
            logger.warning(
                f"MinerUSplitter skipped PDF preprocessing because source file does not exist: {source}"
            )
            return doc

        try:
            return self._parse_pdf_with_pdfplumber(source, metadata=doc.metadata)
        except Exception as exc:
            logger.warning(
                f"MinerUSplitter failed to preprocess '{source}' with pdfplumber, fallback to original content: {exc}"
            )
            return doc

    def split_documents(self, documents: List[Document]) -> List[Document]:
        processed_docs = [self._preprocess_document(doc) for doc in documents]
        splitter = self._get_semantic_splitter()
        semantic_docs = splitter.split_documents(processed_docs)

        final_docs: List[Document] = []
        for doc in semantic_docs:
            content = doc.page_content.strip()
            if not content:
                continue

            if len(content) <= self.max_chunk_size:
                final_docs.append(doc)
                continue

            final_docs.extend(super().split_documents([doc]))

        return final_docs

    def split_text(self, text: str) -> List[str]:
        docs = self.split_documents([Document(page_content=text, metadata={})])
        return [doc.page_content for doc in docs]


class PdfplumberSemanticSplitter(MinerUSplitter):
    pass