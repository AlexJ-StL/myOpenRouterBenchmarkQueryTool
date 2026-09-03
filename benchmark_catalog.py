SOURCES = {
    "artificial-analysis": "Composite indexes from Artificial Analysis (aggregated)",
    "design-arena": "Head-to-head ELO from Design Arena battles",
    "openrouter": "OpenRouter's own evals (GPQA, tau-bench, search benchmarks)",
}

TASK_TYPES = {
    "coding": "Programming and code generation tasks",
    "intelligence": "General reasoning and knowledge",
    "agentic": "Autonomous agent / tool-use tasks",
    "search": "Web search and retrieval-augmented tasks",
}

BENCHMARK_TYPES = {
    "gpqa_diamond": "Graduate-level science and reasoning Q&A (accuracy, 0-1)",
    "tau_bench_verified_airline": "Agentic tool-use on airline customer service (accuracy, 0-1)",
    "search_browsecomp": "Hard multi-hop web research questions (accuracy, 0-1)",
    "search_hle": "Humanity's Last Exam-style questions (accuracy, 0-1)",
    "search_dsqa": "Domain-specific Q&A over documents (accuracy, 0-1)",
    "search_widesearch": "Broad web Q&A, evaluated by item-weighted F1 (0-1)",
}

DESIGN_ARENAS = {
    "models": "General model arena (code + non-code)",
    "builders": "App builder / product builder arena",
    "agents": "Agentic task arena",
}

DESIGN_CATEGORIES = {
    "codecategories": "General coding tasks",
    "uicomponent": "UI component generation",
    "gamedev": "Game development",
    "3d": "3D scene generation",
    "dataviz": "Data visualization",
    "image": "Image generation",
    "video": "Video generation",
    "svg": "SVG generation",
}
