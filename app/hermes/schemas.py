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
    "description": "List all topics (talk outlines) for a given publication code.\n\nArgs:\n    pub_code: Publication code, e.g. 's-34', 'lmd', 'scl'.\n    active_pub: Auto-injected from context (not user-facing).\n\nReturns:\n    Formatted list of available topics with categories.",
    "parameters": {
        "description": "List all topics (talk outlines) for a given publication code.\n\nArgs:\n    pub_code: Publication code, e.g. 's-34', 'lmd', 'scl'.\n    active_pub: Auto-injected from context (not user-facing).\n\nReturns:\n    Formatted list of available topics with categories.",
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
    "description": "Import a talk outline from a JW Library publication into talkmaster.\n\nArgs:\n    topic_query: Topic name or number to search for.\n        Can be the full topic name, a partial match, or \"No 26\"-style.\n        The pub_code is auto-inferred from the last listed/uploaded publication.\n    active_pub: Auto-injected from context (not user-facing).\n\nReturns:\n    Confirmation with imported talk details and its new ID.",
    "parameters": {
        "description": "Import a talk outline from a JW Library publication into talkmaster.\n\nArgs:\n    topic_query: Topic name or number to search for.\n        Can be the full topic name, a partial match, or \"No 26\"-style.\n        The pub_code is auto-inferred from the last listed/uploaded publication.\n    active_pub: Auto-injected from context (not user-facing).\n\nReturns:\n    Confirmation with imported talk details and its new ID.",
        "properties": {
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
    "description": "Create a new revision of a talk with an audience persona and golden thread.\n\nArgs:\n    version_name: Unique name for this revision (e.g., 'v1', 'young-adults').\n    audience_description: Description of the target audience.\n    active_talk_id: Auto-injected from context (not user-facing).\n\nReturns:\n    Confirmation with revision details and next steps.",
    "parameters": {
        "description": "Create a new revision of a talk with an audience persona and golden thread.\n\nArgs:\n    version_name: Unique name for this revision (e.g., 'v1', 'young-adults').\n    audience_description: Description of the target audience.\n    active_talk_id: Auto-injected from context (not user-facing).\n\nReturns:\n    Confirmation with revision details and next steps.",
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
    "description": "AI-develop a single section of a talk revision.\n\nArgs:\n    section_title: Title of the section to develop (partial match OK).\n    active_revision: Auto-injected from context (not user-facing).\n\nReturns:\n    Confirmation or status of the developed section.",
    "parameters": {
        "description": "AI-develop a single section of a talk revision.\n\nArgs:\n    section_title: Title of the section to develop (partial match OK).\n    active_revision: Auto-injected from context (not user-facing).\n\nReturns:\n    Confirmation or status of the developed section.",
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
    "description": "Evaluate a talk revision against the 53-point S-38 rubric.\n\nArgs:\n    active_revision: Auto-injected from context.\n    revision_name: Explicit override (from AI/direct call).\n\nReturns:\n    Trigger confirmation \u2014 scores available via get_evaluation_scores.",
    "parameters": {
        "description": "Evaluate a talk revision against the 53-point S-38 rubric.\n\nArgs:\n    active_revision: Auto-injected from context.\n    revision_name: Explicit override (from AI/direct call).\n\nReturns:\n    Trigger confirmation \u2014 scores available via get_evaluation_scores.",
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
    "description": "Get S-38 rubric evaluation scores for a talk revision.\n\nArgs:\n    active_revision: Auto-injected from context.\n    revision_name: Explicit override.\n\nReturns:\n    Scores broken down by S-38 category with coaching tips.",
    "parameters": {
        "description": "Get S-38 rubric evaluation scores for a talk revision.\n\nArgs:\n    active_revision: Auto-injected from context.\n    revision_name: Explicit override.\n\nReturns:\n    Scores broken down by S-38 category with coaching tips.",
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
    "description": "Generate AI delivery coaching cues for rehearsal of a talk revision.\n\nArgs:\n    active_revision: Auto-injected from context.\n    revision_name: Explicit override.\n\nReturns:\n    Personalized delivery cues: pacing, pauses, emphasis, eye contact.",
    "parameters": {
        "description": "Generate AI delivery coaching cues for rehearsal of a talk revision.\n\nArgs:\n    active_revision: Auto-injected from context.\n    revision_name: Explicit override.\n\nReturns:\n    Personalized delivery cues: pacing, pauses, emphasis, eye contact.",
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
    "description": "Assemble and export the final talk manuscript summary.\n\nArgs:\n    active_revision: Auto-injected from context.\n    revision_name: Explicit override.\n\nReturns:\n    A condensed version of the full manuscript for review.",
    "parameters": {
        "description": "Assemble and export the final talk manuscript summary.\n\nArgs:\n    active_revision: Auto-injected from context.\n    revision_name: Explicit override.\n\nReturns:\n    A condensed version of the full manuscript for review.",
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

