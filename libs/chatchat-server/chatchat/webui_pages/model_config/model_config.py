import streamlit as st

from chatchat.webui_pages.utils import *


def model_config_page(api: ApiRequest):
    init_splitter_config()

    st.subheader("系统配置")
    splitter_names = list(SPLITTER_OPTIONS.keys())
    current_splitter = st.session_state.get("text_splitter_name", Settings.kb_settings.TEXT_SPLITTER_NAME)
    current_index = splitter_names.index(current_splitter) if current_splitter in splitter_names else 0

    splitter_name = st.selectbox(
        "Splitter 类型",
        splitter_names,
        index=current_index,
        format_func=lambda key: SPLITTER_OPTIONS[key],
    )
    st.session_state["text_splitter_name"] = splitter_name

    if splitter_name == "ChineseRecursiveTextSplitter":
        st.caption("当前配置对应原知识库管理页中的文件处理配置。")
        cols = st.columns(3)
        st.session_state["chunk_size"] = cols[0].number_input(
            "单段文本最大长度：",
            1,
            4000,
            value=int(st.session_state.get("chunk_size", Settings.kb_settings.CHUNK_SIZE)),
        )
        st.session_state["chunk_overlap"] = cols[1].number_input(
            "相邻文本重合长度：",
            0,
            int(st.session_state["chunk_size"]),
            value=int(st.session_state.get("chunk_overlap", Settings.kb_settings.OVERLAP_SIZE)),
        )
        st.session_state["zh_title_enhance"] = cols[2].checkbox(
            "开启中文标题加强",
            value=bool(st.session_state.get("zh_title_enhance", Settings.kb_settings.ZH_TITLE_ENHANCE)),
        )
    elif splitter_name in {"MinerUSplitter", "PdfplumberSemanticSplitter"}:
        st.caption("使用 pdfplumber 提取 PDF 正文和表格文本，再执行 SemanticChunker 语义切分。")
        cols = st.columns(2)
        st.session_state["chunk_size"] = cols[0].number_input(
            "最大块长度：",
            1,
            4000,
            value=int(st.session_state.get("chunk_size", Settings.kb_settings.CHUNK_SIZE)),
        )
        st.session_state["chunk_overlap"] = cols[1].number_input(
            "回退切分重叠长度：",
            0,
            int(st.session_state["chunk_size"]),
            value=int(st.session_state.get("chunk_overlap", Settings.kb_settings.OVERLAP_SIZE)),
        )
        cols = st.columns(3)
        st.session_state["breakpoint_threshold_type"] = cols[0].selectbox(
            "切分阈值策略",
            ["percentile", "standard_deviation", "interquartile"],
            index=["percentile", "standard_deviation", "interquartile"].index(
                st.session_state.get("breakpoint_threshold_type", "percentile")
            ),
        )
        st.session_state["breakpoint_threshold_amount"] = cols[1].number_input(
            "breakpoint_threshold_amount",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state.get("breakpoint_threshold_amount", 95.0)),
            step=1.0,
        )
        st.session_state["min_chunk_size"] = cols[2].number_input(
            "min_chunk_size",
            min_value=1,
            max_value=int(st.session_state["chunk_size"]),
            value=int(st.session_state.get("min_chunk_size", 200)),
        )
        st.session_state["zh_title_enhance"] = st.checkbox(
            "开启中文标题加强",
            value=bool(st.session_state.get("zh_title_enhance", Settings.kb_settings.ZH_TITLE_ENHANCE)),
        )

    current = get_splitter_config()
    st.json(current)
