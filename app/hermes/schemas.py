"""AUTO-GENERATED SCHEMAS FROM V1"""

FETCH_DOSSIER = {
    "name": "fetch_dossier",
    "description": "Fetch the user's official profile (Name, District, Language) from RapidPro.\nUse this at the START of a conversation to populate the Dossier.\n\nArgs:\n    urn (str): The user's URN (e.g., \"whatsapp:1234567890\").",
    "parameters": {
        "description": "Fetch the user's official profile (Name, District, Language) from RapidPro.\nUse this at the START of a conversation to populate the Dossier.\n\nArgs:\n    urn (str): The user's URN (e.g., \"whatsapp:1234567890\").",
        "properties": {
            "urn": {
                "type": "string"
            }
        },
        "required": [
            "urn"
        ],
        "type": "object"
    }
}

START_FLOW = {
    "name": "start_flow",
    "description": "Trigger a specific RapidPro flow for the user.\n\nArgs:\n    urn (str): The user's URN.\n    flow_identifier (str): The Name OR UUID of the flow to start.",
    "parameters": {
        "description": "Trigger a specific RapidPro flow for the user.\n\nArgs:\n    urn (str): The user's URN.\n    flow_identifier (str): The Name OR UUID of the flow to start.",
        "properties": {
            "urn": {
                "type": "string"
            },
            "flow_identifier": {
                "type": "string"
            }
        },
        "required": [
            "urn",
            "flow_identifier"
        ],
        "type": "object"
    }
}

CHECK_STOCK = {
    "name": "check_stock",
    "description": "Check if an item is in stock at the Hardware Store.\n\nArgs:\n    item_name (str): The name of the item (e.g., 'Cement', 'Hammer').",
    "parameters": {
        "description": "Check if an item is in stock at the Hardware Store.\n\nArgs:\n    item_name (str): The name of the item (e.g., 'Cement', 'Hammer').",
        "properties": {
            "item_name": {
                "type": "string"
            }
        },
        "required": [
            "item_name"
        ],
        "type": "object"
    }
}

ORDER_DELIVERY = {
    "name": "order_delivery",
    "description": "Schedule a delivery for hardware supplies.\n\nArgs:\n    item_name (str): Items to deliver.\n    address (str): Delivery address.\n    phone (str): Contact number.",
    "parameters": {
        "description": "Schedule a delivery for hardware supplies.\n\nArgs:\n    item_name (str): Items to deliver.\n    address (str): Delivery address.\n    phone (str): Contact number.",
        "properties": {
            "item_name": {
                "type": "string"
            },
            "address": {
                "type": "string"
            },
            "phone": {
                "type": "string"
            }
        },
        "required": [
            "item_name",
            "address",
            "phone"
        ],
        "type": "object"
    }
}

SCHEDULE_VIEWING = {
    "name": "schedule_viewing",
    "description": "Schedule a request to view a real estate property.\n\nArgs:\n    property_id (str): The ID of the property (e.g., 'APT-101').\n    date (str): Preferred date/time.",
    "parameters": {
        "description": "Schedule a request to view a real estate property.\n\nArgs:\n    property_id (str): The ID of the property (e.g., 'APT-101').\n    date (str): Preferred date/time.",
        "properties": {
            "property_id": {
                "type": "string"
            },
            "date": {
                "type": "string"
            }
        },
        "required": [
            "property_id",
            "date"
        ],
        "type": "object"
    }
}

GET_TALKPREP_HELP = {
    "name": "get_talkprep_help",
    "description": "Return an onboarding guide for new TalkPrep users.\n\nReturns:\n    A formatted guide explaining available commands and workflow stages.",
    "parameters": {
        "description": "Return an onboarding guide for new TalkPrep users.\n\nReturns:\n    A formatted guide explaining available commands and workflow stages.",
        "properties": {},
        "type": "object"
    }
}

TALKMASTER_STATUS = {
    "name": "talkmaster_status",
    "description": "Check the current talkmaster status: imported talks, revisions.\n\nReturns:\n    A summary table of imported talks and their revisions.",
    "parameters": {
        "description": "Check the current talkmaster status: imported talks, revisions.\n\nReturns:\n    A summary table of imported talks and their revisions.",
        "properties": {},
        "type": "object"
    }
}

SELECT_ACTIVE_TALK = {
    "name": "select_active_talk",
    "description": "Select a talk as the active context for subsequent operations.\n\nArgs:\n    talk_id: Numeric ID of the talk (from talkmaster_status).\n\nReturns:\n    Confirmation with talk name and available revisions.",
    "parameters": {
        "description": "Select a talk as the active context for subsequent operations.\n\nArgs:\n    talk_id: Numeric ID of the talk (from talkmaster_status).\n\nReturns:\n    Confirmation with talk name and available revisions.",
        "properties": {
            "talk_id": {
                "type": "string"
            }
        },
        "required": [
            "talk_id"
        ],
        "type": "object"
    }
}

LIST_PUBLICATIONS = {
    "name": "list_publications",
    "description": "List all available JW publications in the jwlinker database.\n\nReturns:\n    A formatted list of publications with codes and topic counts.",
    "parameters": {
        "description": "List all available JW publications in the jwlinker database.\n\nReturns:\n    A formatted list of publications with codes and topic counts.",
        "properties": {},
        "type": "object"
    }
}

LIST_TOPICS = {
    "name": "list_topics",
    "description": "List all topics (talk outlines) for a given publication code.\n\nArgs:\n    pub_code: Publication code, e.g. 's-34', 'lmd', 'scl'.\n    active_pub: Infer this from previous tool outputs in memory.\n\nReturns:\n    Formatted list of available topics with categories.",
    "parameters": {
        "description": "List all topics (talk outlines) for a given publication code.\n\nArgs:\n    pub_code: Publication code, e.g. 's-34', 'lmd', 'scl'.\n    active_pub: Infer this from previous tool outputs in memory.\n\nReturns:\n    Formatted list of available topics with categories.",
        "properties": {
            "pub_code": {
                "type": "string"
            },
            "active_pub": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            }
        },
        "required": [
            "pub_code"
        ],
        "type": "object"
    }
}

IMPORT_TALK = {
    "name": "import_talk",
    "description": "Import a talk outline from a JW Library publication into talkmaster.\n\nArgs:\n    pub_code: Optional publication code (e.g. 's-34').\n    topic_query: Topic name or number to search for.\n        Can be the full topic name, a partial match, or \"No 26\"-style.\n        The pub_code is auto-inferred from the last listed/uploaded publication.\n    active_pub: Infer this from previous tool outputs in memory.\n\nReturns:\n    Confirmation with imported talk details and its new ID.",
    "parameters": {
        "description": "Import a talk outline from a JW Library publication into talkmaster.\n\nArgs:\n    pub_code: Optional publication code (e.g. 's-34').\n    topic_query: Topic name or number to search for.\n        Can be the full topic name, a partial match, or \"No 26\"-style.\n        The pub_code is auto-inferred from the last listed/uploaded publication.\n    active_pub: Infer this from previous tool outputs in memory.\n\nReturns:\n    Confirmation with imported talk details and its new ID.",
        "properties": {
            "pub_code": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            },
            "topic_query": {
                "type": "string"
            },
            "active_pub": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            }
        },
        "required": [
            "topic_query"
        ],
        "type": "object"
    }
}

CREATE_REVISION = {
    "name": "create_revision",
    "description": "Create a new revision of a talk with an audience persona and golden thread.\n\nArgs:\n    version_name: Unique name for this revision (e.g., 'v1', 'young-adults').\n    audience_description: Description of the target audience.\n    active_talk_id: Infer this from previous tool outputs in memory.\n\nReturns:\n    Confirmation with revision details and next steps.",
    "parameters": {
        "description": "Create a new revision of a talk with an audience persona and golden thread.\n\nArgs:\n    version_name: Unique name for this revision (e.g., 'v1', 'young-adults').\n    audience_description: Description of the target audience.\n    active_talk_id: Infer this from previous tool outputs in memory.\n\nReturns:\n    Confirmation with revision details and next steps.",
        "properties": {
            "version_name": {
                "type": "string"
            },
            "audience_description": {
                "default": "General congregation audience",
                "type": "string"
            },
            "active_talk_id": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            }
        },
        "required": [
            "version_name"
        ],
        "type": "object"
    }
}

DEVELOP_SECTION = {
    "name": "develop_section",
    "description": "AI-develop a single section of a talk revision.\n\nArgs:\n    section_title: Title of the section to develop (partial match OK).\n    active_revision: Infer this from previous tool outputs in memory.\n\nReturns:\n    Confirmation or status of the developed section.",
    "parameters": {
        "description": "AI-develop a single section of a talk revision.\n\nArgs:\n    section_title: Title of the section to develop (partial match OK).\n    active_revision: Infer this from previous tool outputs in memory.\n\nReturns:\n    Confirmation or status of the developed section.",
        "properties": {
            "section_title": {
                "type": "string"
            },
            "active_revision": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            }
        },
        "required": [
            "section_title"
        ],
        "type": "object"
    }
}

EVALUATE_TALK = {
    "name": "evaluate_talk",
    "description": "Evaluate a talk revision against the 53-point S-38 rubric.\n\nArgs:\n    active_revision: Infer this from previous tool outputs in memory.\n    revision_name: Explicit override (from AI/direct call).\n\nReturns:\n    Trigger confirmation \u2014 scores available via get_evaluation_scores.",
    "parameters": {
        "description": "Evaluate a talk revision against the 53-point S-38 rubric.\n\nArgs:\n    active_revision: Infer this from previous tool outputs in memory.\n    revision_name: Explicit override (from AI/direct call).\n\nReturns:\n    Trigger confirmation \u2014 scores available via get_evaluation_scores.",
        "properties": {
            "active_revision": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            },
            "revision_name": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            }
        },
        "type": "object"
    }
}

GET_EVALUATION_SCORES = {
    "name": "get_evaluation_scores",
    "description": "Get S-38 rubric evaluation scores for a talk revision.\n\nArgs:\n    active_revision: Infer this from previous tool outputs in memory.\n    revision_name: Explicit override.\n\nReturns:\n    Scores broken down by S-38 category with coaching tips.",
    "parameters": {
        "description": "Get S-38 rubric evaluation scores for a talk revision.\n\nArgs:\n    active_revision: Infer this from previous tool outputs in memory.\n    revision_name: Explicit override.\n\nReturns:\n    Scores broken down by S-38 category with coaching tips.",
        "properties": {
            "active_revision": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            },
            "revision_name": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            }
        },
        "type": "object"
    }
}

REHEARSAL_CUE = {
    "name": "rehearsal_cue",
    "description": "Generate AI delivery coaching cues for rehearsal of a talk revision.\n\nArgs:\n    active_revision: Infer this from previous tool outputs in memory.\n    revision_name: Explicit override.\n\nReturns:\n    Personalized delivery cues: pacing, pauses, emphasis, eye contact.",
    "parameters": {
        "description": "Generate AI delivery coaching cues for rehearsal of a talk revision.\n\nArgs:\n    active_revision: Infer this from previous tool outputs in memory.\n    revision_name: Explicit override.\n\nReturns:\n    Personalized delivery cues: pacing, pauses, emphasis, eye contact.",
        "properties": {
            "active_revision": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            },
            "revision_name": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            }
        },
        "type": "object"
    }
}

EXPORT_TALK_SUMMARY = {
    "name": "export_talk_summary",
    "description": "Assemble and export the final talk manuscript summary.\n\nArgs:\n    active_revision: Infer this from previous tool outputs in memory.\n    revision_name: Explicit override.\n\nReturns:\n    A condensed version of the full manuscript for review.",
    "parameters": {
        "description": "Assemble and export the final talk manuscript summary.\n\nArgs:\n    active_revision: Infer this from previous tool outputs in memory.\n    revision_name: Explicit override.\n\nReturns:\n    A condensed version of the full manuscript for review.",
        "properties": {
            "active_revision": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            },
            "revision_name": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            }
        },
        "type": "object"
    }
}

COST_REPORT = {
    "name": "cost_report",
    "description": "Show LLM token usage and estimated cost for the current talkmaster session.\n\nReturns:\n    Token counts and estimated USD cost for this preparation session.",
    "parameters": {
        "description": "Show LLM token usage and estimated cost for the current talkmaster session.\n\nReturns:\n    Token counts and estimated USD cost for this preparation session.",
        "properties": {},
        "type": "object"
    }
}

GENERATE_ANKI_DECK = {
    "name": "generate_anki_deck",
    "description": "Generate an Anki flashcard deck (.apkg) from a JW publication in the database.\n\nThe deck is saved and a download URL is returned so the user can\nfetch the .apkg file directly. If no topic is specified, all topics\nfor the publication are included.\n\nArgs:\n    pub_code: Publication code (e.g., 's34', 'lmd', 'scl').\n    topic_name: Optional topic name filter (partial match OK).\n\nReturns:\n    Download URL for the generated .apkg file, or an error message.",
    "parameters": {
        "description": "Generate an Anki flashcard deck (.apkg) from a JW publication in the database.\n\nThe deck is saved and a download URL is returned so the user can\nfetch the .apkg file directly. If no topic is specified, all topics\nfor the publication are included.\n\nArgs:\n    pub_code: Publication code (e.g., 's34', 'lmd', 'scl').\n    topic_name: Optional topic name filter (partial match OK).\n\nReturns:\n    Download URL for the generated .apkg file, or an error message.",
        "properties": {
            "pub_code": {
                "type": "string"
            },
            "topic_name": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            }
        },
        "required": [
            "pub_code"
        ],
        "type": "object"
    }
}

PUSH_TO_SIYUAN = {
    "name": "push_to_siyuan",
    "description": "Push JW publication content to SiYuan as a structured document tree.\n\nCreates a two-level tree (sections \u2192 lessons) with scripture links and\nspaced-repetition flashcards. Requires SIYUAN_NOTEBOOK_ID env var.\n\nArgs:\n    pub_code: Publication code (e.g., 's34', 'lmd', 'scl').\n    topic_name: Optional topic name filter (partial match OK).\n\nReturns:\n    SiYuan root document ID, or an error message.",
    "parameters": {
        "description": "Push JW publication content to SiYuan as a structured document tree.\n\nCreates a two-level tree (sections \u2192 lessons) with scripture links and\nspaced-repetition flashcards. Requires SIYUAN_NOTEBOOK_ID env var.\n\nArgs:\n    pub_code: Publication code (e.g., 's34', 'lmd', 'scl').\n    topic_name: Optional topic name filter (partial match OK).\n\nReturns:\n    SiYuan root document ID, or an error message.",
        "properties": {
            "pub_code": {
                "type": "string"
            },
            "topic_name": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            }
        },
        "required": [
            "pub_code"
        ],
        "type": "object"
    }
}

UPLOAD_JWPUB = {
    "name": "upload_jwpub",
    "description": "Process a .jwpub file from a WhatsApp attachment URL.\n\nDownloads the file, decrypts it, and extracts all topics into the\nJWLinker database so they can be imported into TalkMaster.\n\nArgs:\n    media_url: The download URL for the .jwpub file (from WhatsApp attachment).\n    pub_code: Optional publication code override (auto-detected from file if omitted).\n\nReturns:\n    Summary of extracted topics, or an error message.",
    "parameters": {
        "description": "Process a .jwpub file from a WhatsApp attachment URL.\n\nDownloads the file, decrypts it, and extracts all topics into the\nJWLinker database so they can be imported into TalkMaster.\n\nArgs:\n    media_url: The download URL for the .jwpub file (from WhatsApp attachment).\n    pub_code: Optional publication code override (auto-detected from file if omitted).\n\nReturns:\n    Summary of extracted topics, or an error message.",
        "properties": {
            "media_url": {
                "type": "string"
            },
            "pub_code": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": None
            }
        },
        "required": [
            "media_url"
        ],
        "type": "object"
    }
}

SUBMIT_FORM = {
    "name": "submit_form",
    "description": "Submit a completed form from the RiveBot multi-turn flow.\n\nArgs:\n    form_type: The type of form (e.g., \"support\", \"upgrade\").\n    data: The collected form data as a space-separated string.\n    user_id: The user who submitted the form.\n\nReturns:\n    A confirmation message for the user.",
    "parameters": {
        "description": "Submit a completed form from the RiveBot multi-turn flow.\n\nArgs:\n    form_type: The type of form (e.g., \"support\", \"upgrade\").\n    data: The collected form data as a space-separated string.\n    user_id: The user who submitted the form.\n\nReturns:\n    A confirmation message for the user.",
        "properties": {
            "form_type": {
                "type": "string"
            },
            "data": {
                "type": "string"
            },
            "user_id": {
                "default": "unknown",
                "type": "string"
            }
        },
        "required": [
            "form_type",
            "data"
        ],
        "type": "object"
    }
}

# ── SiYuan Read Tools ────────────────────────────────────────────────────────

SIYUAN_SEARCH = {
    "name": "siyuan_search",
    "description": (
        "Search the knowledge wiki (SiYuan) for information. Use this to find "
        "study notes, talk preparation materials, research summaries, and any "
        "previously saved knowledge. Returns matching blocks with content previews."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query — keywords or phrases to find in the wiki."
            },
            "notebook": {
                "type": "string",
                "description": "Optional: notebook name to scope the search."
            },
        },
        "required": ["query"],
    },
}

SIYUAN_READ = {
    "name": "siyuan_read",
    "description": (
        "Read a specific wiki page by its ID. Use after siyuan_search to read "
        "the full content of a search result. Returns clean markdown."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "Block ID of the document to read (from siyuan_search results)."
            },
        },
        "required": ["doc_id"],
    },
}

# ── SiYuan Wiki Tools (LLM Wiki pattern) ────────────────────────────────────

SIYUAN_LIST_DOCS = {
    "name": "siyuan_list_docs",
    "description": (
        "List documents in a SiYuan notebook path. Returns document names and IDs. "
        "Use to browse the wiki tree structure and discover existing pages."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "notebook": {
                "type": "string",
                "description": "Notebook name (e.g., 'Wiki')."
            },
            "path": {
                "type": "string",
                "description": "Path within the notebook. Use '/' for root. Default: '/'."
            },
        },
        "required": ["notebook"],
    },
}

SIYUAN_CREATE_NOTEBOOK = {
    "name": "siyuan_create_notebook",
    "description": "Create a new SiYuan notebook. Returns the notebook ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Human-readable notebook name."
            },
        },
        "required": ["name"],
    },
}

SIYUAN_CREATE_DOC = {
    "name": "siyuan_create_doc",
    "description": (
        "Create a new document in a SiYuan notebook. Use for wiki pages: entities, "
        "concepts, comparisons, raw sources. The path determines the document's "
        "position in the tree (e.g., '/entities/my-entity')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "notebook": {
                "type": "string",
                "description": "Notebook name (e.g., 'Wiki')."
            },
            "path": {
                "type": "string",
                "description": "Document path (e.g., '/entities/transformer-architecture')."
            },
            "markdown": {
                "type": "string",
                "description": "Markdown content for the new document."
            },
        },
        "required": ["notebook", "path", "markdown"],
    },
}

SIYUAN_UPDATE_BLOCK = {
    "name": "siyuan_update_block",
    "description": (
        "Replace a block's content with new markdown. Use to update existing wiki "
        "pages. Get the block ID from siyuan_search or siyuan_read results."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "block_id": {
                "type": "string",
                "description": "ID of the block to update."
            },
            "markdown": {
                "type": "string",
                "description": "New markdown content to replace the block's current content."
            },
        },
        "required": ["block_id", "markdown"],
    },
}

SIYUAN_APPEND_BLOCK = {
    "name": "siyuan_append_block",
    "description": (
        "Append markdown content to an existing SiYuan page. Use to add new "
        "information to a page without replacing existing content — for example, "
        "appending a log entry or adding a new section to a wiki page."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "notebook": {
                "type": "string",
                "description": "Notebook name."
            },
            "path": {
                "type": "string",
                "description": "Document path within the notebook."
            },
            "markdown": {
                "type": "string",
                "description": "Markdown content to append."
            },
        },
        "required": ["notebook", "path", "markdown"],
    },
}

SIYUAN_SET_ATTRS = {
    "name": "siyuan_set_attrs",
    "description": (
        "Set custom attributes on a SiYuan block (replaces YAML frontmatter). "
        "Use for wiki metadata: type, tags, confidence, sources, dates. "
        "Keys are auto-prefixed with 'custom-' if not already prefixed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "block_id": {
                "type": "string",
                "description": "Block ID to set attributes on."
            },
            "attrs": {
                "type": "object",
                "description": (
                    "Key-value pairs. Example: {\"type\": \"entity\", \"tags\": \"model,architecture\", "
                    "\"confidence\": \"high\", \"created\": \"2026-04-29\"}"
                ),
            },
        },
        "required": ["block_id", "attrs"],
    },
}

SIYUAN_GET_ATTRS = {
    "name": "siyuan_get_attrs",
    "description": "Get all attributes of a SiYuan block. Returns custom metadata like type, tags, confidence.",
    "parameters": {
        "type": "object",
        "properties": {
            "block_id": {
                "type": "string",
                "description": "Block ID to get attributes for."
            },
        },
        "required": ["block_id"],
    },
}

SIYUAN_SQL_QUERY = {
    "name": "siyuan_sql_query",
    "description": (
        "Execute a read-only SQL SELECT query against SiYuan's block database. "
        "Useful for wiki lint operations: finding orphan pages, checking tags, "
        "listing pages by type. Only SELECT statements are allowed. "
        "Key columns: id, parent_id, root_id, box (notebook ID), path, content, "
        "type (d=doc, p=paragraph, h=heading), created, updated."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "SQL SELECT statement. Example: SELECT id, content FROM blocks WHERE type='d' LIMIT 20"
            },
        },
        "required": ["sql"],
    },
}

SIYUAN_DELETE_BLOCK = {
    "name": "siyuan_delete_block",
    "description": "Delete a SiYuan block by ID. Use with caution — this is permanent.",
    "parameters": {
        "type": "object",
        "properties": {
            "block_id": {
                "type": "string",
                "description": "Block ID to delete."
            },
        },
        "required": ["block_id"],
    },
}

SIYUAN_RENAME_DOC = {
    "name": "siyuan_rename_doc",
    "description": "Rename a SiYuan document. Changes the document's title in the tree.",
    "parameters": {
        "type": "object",
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "Document root block ID."
            },
            "title": {
                "type": "string",
                "description": "New document title."
            },
        },
        "required": ["doc_id", "title"],
    },
}

SIYUAN_INIT_WIKI = {
    "name": "siyuan_init_wiki",
    "description": (
        "Bootstrap a new LLM Wiki in SiYuan. Creates a notebook with Schema, Index, "
        "and Log documents, plus directory structure (raw/, entities/, concepts/, "
        "comparisons/, queries/). Use this once to set up a new wiki — then use "
        "the other siyuan_* tools to populate it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Notebook name (default: 'Wiki')."
            },
            "domain": {
                "type": "string",
                "description": "What this wiki covers (e.g., 'AI/ML research', 'IIAB infrastructure')."
            },
            "tags": {
                "type": "string",
                "description": "Initial tag taxonomy as multi-line text. Leave empty for defaults."
            },
        },
        "required": ["domain"],
    },
}

SIYUAN_GET_BACKLINKS = {
    "name": "siyuan_get_backlinks",
    "description": (
        "Get all blocks that reference (link to) a given document. Returns the "
        "backlinks — essential for wiki lint to find orphan pages (pages with zero "
        "inbound references). Also useful for understanding how a concept connects "
        "to the rest of the wiki."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "Document root block ID to find backlinks for."
            },
        },
        "required": ["doc_id"],
    },
}

SIYUAN_GET_CHILDREN = {
    "name": "siyuan_get_children",
    "description": (
        "Get the child blocks of a block (the block tree). Returns block IDs and "
        "types (h=heading, p=paragraph, l=list, etc.). Use to navigate document "
        "structure — for example, finding the block ID of a specific heading to "
        "update just that section."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "block_id": {
                "type": "string",
                "description": "Parent block ID (typically a document root block)."
            },
        },
        "required": ["block_id"],
    },
}

SIYUAN_GET_HPATH = {
    "name": "siyuan_get_hpath",
    "description": (
        "Convert a block ID to a human-readable document path. For example, "
        "converts '20260429041444-wppl57p' to '/entities/kubernetes'. Use when "
        "displaying results to the user or building cross-references."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "block_id": {
                "type": "string",
                "description": "Block ID to resolve."
            },
        },
        "required": ["block_id"],
    },
}

SIYUAN_REMOVE_DOC = {
    "name": "siyuan_remove_doc",
    "description": (
        "Permanently delete a SiYuan document. Use for archiving superseded wiki "
        "pages. This is irreversible — use with caution. Before deleting, update "
        "any pages that link to the document being removed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "Document root block ID to delete."
            },
        },
        "required": ["doc_id"],
    },
}

SIYUAN_UPSERT_PAGE = {
    "name": "siyuan_upsert_page",
    "description": (
        "Create or update a wiki page by path. If the page already exists at the "
        "given path, its content is replaced. If it doesn't exist, a new page is "
        "created. This is the preferred tool for wiki ingest — avoids manual "
        "search-then-decide-create-or-update logic."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "notebook": {
                "type": "string",
                "description": "Notebook name (e.g., 'Life', 'IIAB')."
            },
            "path": {
                "type": "string",
                "description": "Page path within the notebook (e.g., '/people/mom', '/concepts/kubernetes')."
            },
            "markdown": {
                "type": "string",
                "description": "Full markdown content for the page."
            },
        },
        "required": ["notebook", "path", "markdown"],
    },
}

SIYUAN_LINT = {
    "name": "siyuan_lint",
    "description": (
        "Run 10 wiki quality rules against a SiYuan notebook and return a "
        "structured lint report. Checks for: broken refs, orphan pages, "
        "missing attributes, duplicate titles, empty pages, low confidence, "
        "contradictions, stale pages, cross-link minimums, and index completeness. "
        "Use when the user asks to audit, health-check, or lint their wiki."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "notebook": {
                "type": "string",
                "description": "Notebook name to lint (e.g., 'Life', 'IIAB')."
            },
        },
        "required": ["notebook"],
    },
}

SIYUAN_DASHBOARD = {
    "name": "siyuan_dashboard",
    "description": (
        "Generate an on-demand dashboard from SiYuan wiki data. "
        "Available dashboards:\n"
        "• crm_health — People directory stats, contact freshness, circle breakdown\n"
        "• recent_contacts — People sorted by last-contact date with freshness indicators\n"
        "• wiki_quality — Formatted lint report with errors, warnings, info\n"
        "• habits — Active habits, streaks, daily/weekly compliance\n"
        "• goals — Goal status breakdown with progress bars and overdue alerts\n\n"
        "Use when the user asks about their contacts, habits, goals, or wiki health."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "dashboard_type": {
                "type": "string",
                "enum": ["crm_health", "recent_contacts", "wiki_quality", "habits", "goals"],
                "description": "Type of dashboard to generate."
            },
            "notebook": {
                "type": "string",
                "description": "Notebook name (default: 'Life')."
            },
        },
        "required": ["dashboard_type"],
    },
}

# ── CRM Operations (ADR-010) ────────────────────────────────────────────────

START_CRM_OPS = {
    "name": "start_crm_ops",
    "description": (
        "Start the CRM operations flow for the admin user. "
        "Triggers a RapidPro flow that provides a WhatsApp menu for workspace "
        "management. Returns {{noreply}} to suppress AI response."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "Admin URN (auto-injected by macro bridge)."
            }
        },
        "required": ["user_id"],
    },
}

SEND_CRM_HELP = {
    "name": "send_crm_help",
    "description": (
        "Send a WhatsApp Quick Reply button explaining how to access CRM operations. "
        "Use when the admin asks how to manage contacts, access workspace ops, or trigger admin menus. "
        "Returns {{noreply}} (button is sent directly via WuzAPI)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "Admin URN (auto-injected by macro bridge)."
            }
        },
        "required": ["user_id"],
    },
}

# ── Layer 2 Direct Commands (ADR-011 T2) ─────────────────────────────────────

CRM_LIST_GROUPS = {
    "name": "crm_list_groups",
    "description": "List all RapidPro segments (groups) with member counts. Instant single-message response.",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

CRM_LOOKUP_CONTACT = {
    "name": "crm_lookup_contact",
    "description": "Look up a contact by phone number. Returns name, segments, language, and fields.",
    "parameters": {
        "type": "object",
        "properties": {
            "phone": {
                "type": "string",
                "description": "Phone number to look up (digits only)."
            }
        },
        "required": ["phone"],
    },
}

CRM_ORG_INFO = {
    "name": "crm_org_info",
    "description": "Show RapidPro organization info: name, timezone, languages, credits.",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

CRM_CREATE_GROUP = {
    "name": "crm_create_group",
    "description": "Create a new RapidPro segment (group).",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name for the new segment."
            }
        },
        "required": ["name"],
    },
}

# ── System Operations (ADR-011 migration) ────────────────────────────────────

MACRO_RESET = {
    "name": "macro_reset",
    "description": "Reset the current user's conversation session (clear Hermes memory).",
    "parameters": {"type": "object", "properties": {}},
}

MACRO_DEBUG = {
    "name": "macro_debug",
    "description": "Return system diagnostics for the current user.",
    "parameters": {"type": "object", "properties": {}},
}

MACRO_NOAI = {
    "name": "macro_noai",
    "description": "Disable AI for the calling user only.",
    "parameters": {"type": "object", "properties": {}},
}

MACRO_NOAI_GLOBAL = {
    "name": "macro_noai_global",
    "description": "Disable AI for ALL users globally (admin only).",
    "parameters": {"type": "object", "properties": {}},
}

MACRO_NOAI_STATUS = {
    "name": "macro_noai_status",
    "description": "Show current noai state: global flag and per-user overrides.",
    "parameters": {"type": "object", "properties": {}},
}

MACRO_ENABLEAI = {
    "name": "macro_enableai",
    "description": "Re-enable AI for the calling user.",
    "parameters": {"type": "object", "properties": {}},
}

MACRO_ENABLEAI_GLOBAL = {
    "name": "macro_enableai_global",
    "description": "Re-enable AI for ALL users globally (admin only).",
    "parameters": {"type": "object", "properties": {}},
}

MACRO_RELOAD = {
    "name": "macro_reload",
    "description": "Reload all RiveBot brain files and re-initialize persona engines.",
    "parameters": {"type": "object", "properties": {}},
}

MACRO_HEALTH = {
    "name": "macro_health",
    "description": "Check health of all ecosystem services (gateway, rivebot, siyuan).",
    "parameters": {"type": "object", "properties": {}},
}

MACRO_SKILLS = {
    "name": "macro_skills",
    "description": "List or delete Hermes agent-created skills.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "list or delete"},
            "skill_name": {"type": "string", "description": "Name of skill to delete."},
        },
    },
}

MACRO_FLOW = {
    "name": "macro_flow",
    "description": "Start or stop a RapidPro flow for the calling user.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "start or stop"},
            "flow_uuid": {"type": "string", "description": "UUID of the flow to start."},
        },
        "required": ["action"],
    },
}

# ── Config Operations (ADR-011 migration) ────────────────────────────────────

MACRO_PERSONA = {
    "name": "macro_persona",
    "description": "Persona CRUD: list, show, create, delete.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "list, show, create, or delete"},
        },
        "required": ["action"],
    },
}

MACRO_CHANNEL = {
    "name": "macro_channel",
    "description": "Channel-persona mapping: list, assign.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "list or assign"},
        },
        "required": ["action"],
    },
}

MACRO_ADMIN = {
    "name": "macro_admin",
    "description": "Admin permission management: list, add, remove.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "list, add, or remove"},
        },
        "required": ["action"],
    },
}

MACRO_GLOBAL = {
    "name": "macro_global",
    "description": "RapidPro globals management: get, set.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "get or set"},
            "key": {"type": "string", "description": "Global variable name."},
        },
        "required": ["action", "key"],
    },
}

MACRO_LABEL = {
    "name": "macro_label",
    "description": "Label management: add.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "add"},
            "name": {"type": "string", "description": "Label name."},
        },
        "required": ["action", "name"],
    },
}

