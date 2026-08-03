"""
chatbot.py
Advanced rule-based AI Assistant for Project Report Generator.

No external AI API, no API key required - pure Python keyword matching,
upgraded with:
  1. A broader knowledge base (more topics than a basic FAQ bot)
  2. Conversation memory (understands follow-ups like "give me an example")
  3. Report-awareness (tailors answers to the report you're currently working on)

Design note: get_reply() is intentionally the single entry point. If you ever
want to plug in a real AI model later (e.g. Claude via the anthropic package),
you'd only need to change the inside of this function - app.py never has to change.
"""

import random

GREETING_WORDS = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
THANKS_WORDS = ["thank", "thanks", "thank you", "thx"]
BYE_WORDS = ["bye", "goodbye", "see you", "exit", "quit"]
FOLLOWUP_WORDS = ["example", "more", "elaborate", "explain further", "go on",
                  "continue", "what about", "can you show", "give me one"]

KNOWLEDGE_BASE = {
    "report_meaning": {
        "keywords": ["what is a project report", "project report meaning", "why report",
                     "purpose of report", "what is report"],
        "response": ("A project report is a formal document that explains your entire "
                     "project — the problem, how you built it, the tools you used, the "
                     "results, and what you learned. It exists so evaluators (and anyone "
                     "else) can understand and judge your work without watching you build "
                     "it step by step."),
        "example": ("Think of it like this: if two people, one who saw your project run "
                     "live and one who only read your report, both got quizzed on it, "
                     "the report reader should be able to answer just as well."),
    },
    "abstract": {
        "keywords": ["abstract", "summary of project"],
        "response": ("The Abstract is a short paragraph (150-250 words) at the very start "
                     "that summarizes your whole project — the problem, your solution, the "
                     "technology used, and the result. Someone should understand your entire "
                     "project just from reading it."),
        "example": ("A quick structure: one line on the problem, one to two lines on your "
                     "solution, one line on the tech used, one to two lines on the outcome."),
    },
    "introduction": {
        "keywords": ["introduction", "intro chapter"],
        "response": ("The Introduction gives background — why the problem matters — before "
                     "diving into technical details. It should cover: the general situation, "
                     "what's wrong with the current approach, your objective, and a one-line "
                     "preview of your solution."),
        "example": ("Example flow: 'Manual attendance is common in colleges' -> 'but it's "
                     "time-consuming and prone to proxy attendance' -> 'this project builds "
                     "an automated face-recognition system to solve that.'"),
    },
    "architecture": {
        "keywords": ["architecture", "system design", "block diagram", "how components connect"],
        "response": ("System Architecture shows how the different parts of your system "
                     "connect — usually with a block diagram (frontend -> backend -> "
                     "database/processing -> output), plus a short explanation of each "
                     "block's role and how data flows between them."),
        "example": ("For a web app: Browser -> Flask routes -> SQLite database -> "
                     "back to Browser as a rendered page. Draw that as boxes and arrows."),
    },
    "implementation": {
        "keywords": ["implementation", "how did you build", "logic", "algorithm"],
        "response": ("Implementation is the technical 'how' — the actual logic, algorithms, "
                     "or code approach used to build each part. Cover: key modules and what "
                     "each does, important logic in plain English (not raw code dumps), and "
                     "the tools/libraries used and why."),
        "example": None,
    },
    "results": {
        "keywords": ["results", "output section", "screenshots", "accuracy"],
        "response": ("Results show what actually happened when you tested the project — "
                     "screenshots, sample outputs, and any measurable outcome like accuracy "
                     "or speed, plus a brief interpretation of what it means."),
        "example": None,
    },
    "conclusion": {
        "keywords": ["conclusion", "closing chapter"],
        "response": ("The Conclusion restates the problem in one line, states what was "
                     "achieved, and briefly notes limitations or future improvements. "
                     "No new information should be introduced here."),
        "example": None,
    },
    "references": {
        "keywords": ["reference", "citation", "bibliography", "sources"],
        "response": ("References list every external source — papers, docs, tools — that "
                     "informed your project, numbered in a consistent format (IEEE or APA). "
                     "It's about giving credit and letting readers verify or dig deeper."),
        "example": ('IEEE style example: [1] F. Schroff et al., "FaceNet: A Unified '
                     'Embedding for Face Recognition and Clustering," CVPR, 2015.'),
    },
    "plagiarism": {
        "keywords": ["plagiarism", "copy paste", "unique content", "originality"],
        "response": ("Keep your report in your own words, even when explaining standard "
                     "concepts. It's fine to reference papers or docs (with a citation), "
                     "but don't copy paragraphs directly — rephrase in your own understanding."),
        "example": None,
    },
    "word_count": {
        "keywords": ["word count", "how long should", "how many pages", "page limit"],
        "response": ("There's no strict universal number, but as a rough guide: Abstract "
                     "150-250 words, each main chapter 300-600 words, and a full mini-project "
                     "report usually lands around 15-25 pages total. Follow your guide's "
                     "specific requirement if one is given."),
        "example": None,
    },
    "template": {
        "keywords": ["template", "which category", "project type", "which template"],
        "response": ("Pick the template that matches your project type — Mini Project, "
                     "Major Project, Internship, Research Paper, Seminar Report, or "
                     "Industrial Training. Each one pre-structures the chapters to match "
                     "what's expected for that kind of submission."),
        "example": None,
    },
    "export": {
        "keywords": ["export", "download", "pdf", "docx", "word file", "save report"],
        "response": ("Once your report is generated, you can download it as PDF or DOCX "
                     "from the Preview page — PDF for submission-ready formatting, DOCX if "
                     "you want to keep editing it in Word."),
        "example": None,
    },
    "how_it_works": {
        "keywords": ["how to use", "how does this work", "how do i start", "getting started"],
        "response": ("Quick path: pick a template on the Templates page, fill in the "
                     "guided form chapter by chapter, hit Preview to check it, then "
                     "download as PDF or DOCX. You can also Save Draft anytime and "
                     "come back to it later from My Drafts."),
        "example": None,
    },
}


def _match_topic(text):
    """Return the best-matching topic key for a piece of text, or None."""
    text = text.lower()
    best_topic, best_score = None, 0
    for topic, info in KNOWLEDGE_BASE.items():
        score = sum(1 for kw in info["keywords"] if kw in text)
        if score > best_score:
            best_score, best_topic = score, topic
    return best_topic


def _find_last_topic(history):
    """Look back through the conversation for the last topic the user asked about."""
    for entry in reversed(history or []):
        if entry.get("role") == "user":
            topic = _match_topic(entry.get("text", ""))
            if topic:
                return topic
    return None


def _personalize(response, report_context):
    if not report_context:
        return response
    title = report_context.get("title")
    category = report_context.get("category")
    if title:
        return (f"{response}\n\n(Since you're working on \"{title}\""
                f"{' — a ' + category + ' project' if category else ''} — "
                f"keep this section focused on that.)")
    return response


def get_reply(message, history=None, report_context=None):
    """
    Main entry point. Returns a plain-text reply.
    history: list of {"role": "user"|"bot", "text": "..."} from the Flask session
    report_context: {"title": ..., "category": ...} or None
    """
    history = history or []
    text = message.lower().strip()

    if not text:
        return "Type a question and I'll do my best to help!"

    if any(w in text for w in GREETING_WORDS):
        if report_context and report_context.get("title"):
            return (f"Hey! I see you're working on \"{report_context['title']}\". "
                     "Ask me about any section — Abstract, Introduction, Architecture, "
                     "Results, Conclusion, References — and I'll help.")
        return "Hi! Ask me anything about writing your project report."

    if any(w in text for w in THANKS_WORDS):
        return random.choice([
            "You're welcome! Let me know if you need anything else.",
            "Anytime! Good luck with the report.",
        ])

    if any(w in text for w in BYE_WORDS):
        return "Good luck with your report! Come back anytime you're stuck."

    if any(w in text for w in FOLLOWUP_WORDS):
        last_topic = _find_last_topic(history)
        if last_topic and KNOWLEDGE_BASE[last_topic].get("example"):
            return _personalize(KNOWLEDGE_BASE[last_topic]["example"], report_context)
        if last_topic:
            return _personalize(
                "I don't have a separate example for that one, but here's the main "
                "point again: " + KNOWLEDGE_BASE[last_topic]["response"], report_context)
        return "Sure — what topic would you like an example for?"

    topic = _match_topic(text)
    if topic:
        return _personalize(KNOWLEDGE_BASE[topic]["response"], report_context)

    return ("I'm not sure about that one yet. Try asking about: Abstract, Introduction, "
            "System Architecture, Implementation, Results, Conclusion, References, "
            "Templates, or how to Export your report.")