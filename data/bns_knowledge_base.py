"""
LEX-INDIC: BNS TRANSITION ENGINE
BNS Knowledge Base — Curated legal data for RAG (Retrieval-Augmented Generation)

This file is the "legal brain" of the system. It contains structured knowledge about
the Bharatiya Nyaya Sanhita (BNS) 2023, which replaced the Indian Penal Code (IPC) 1860.
Each entry is a "document" that will be loaded into ChromaDB for vector search.
"""

BNS_SECTIONS = [
    # ─── DOMESTIC VIOLENCE & MATRIMONIAL OFFENCES ─────────────────────────────
    {
        "id": "bns_85",
        "section": "BNS Section 85",
        "old_ipc": "IPC Section 498A",
        "title": "Cruelty by Husband or His Relatives",
        "description": (
            "Whoever, being the husband or the relative of the husband of a woman, "
            "subjects such woman to cruelty shall be punished with imprisonment for a "
            "term which may extend to three years and shall also be liable to fine. "
            "'Cruelty' includes wilful conduct likely to drive the woman to suicide, "
            "grave injury, or harassment to coerce her or her relatives to meet any "
            "unlawful demand for property or valuable security (dowry harassment)."
        ),
        "punishment": "Up to 3 years imprisonment + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes — police can arrest without warrant",
        "keywords": ["cruelty", "husband", "wife", "matrimonial", "domestic", "dowry harassment",
                     "mental cruelty", "physical cruelty", "in-laws", "relatives"],
        "transition_note": "Directly replaces IPC 498A with same scope. Cognizable & Non-bailable.",
    },
    {
        "id": "bns_84",
        "section": "BNS Section 84",
        "old_ipc": "IPC Section 304B",
        "title": "Dowry Death",
        "description": (
            "Where the death of a woman is caused by burns, bodily injury, or occurs "
            "under suspicious circumstances within seven years of marriage, and it is "
            "shown that before her death she was subjected to cruelty or harassment by "
            "her husband or his relatives in connection with demand for dowry, such death "
            "shall be called 'dowry death' and such husband or relatives shall be deemed "
            "to have caused her death."
        ),
        "punishment": "Minimum 7 years, may extend to life imprisonment",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["dowry death", "burn", "suspicious death", "seven years", "marriage",
                     "harassment", "dowry", "murder", "death"],
        "transition_note": "Replaces IPC 304B. Minimum sentence is 7 years. Presumption of guilt on accused.",
    },
    {
        "id": "bns_80",
        "section": "BNS Section 80",
        "old_ipc": "IPC Section 304",
        "title": "Culpable Homicide not Amounting to Murder",
        "description": (
            "Whoever commits culpable homicide not amounting to murder shall be punished. "
            "If the act by which the death is caused is done with the intention of causing "
            "death, or of causing such bodily injury as is likely to cause death — "
            "imprisonment for life or up to 10 years and fine. "
            "If done with knowledge that it is likely to cause death — up to 10 years and fine."
        ),
        "punishment": "Life imprisonment or up to 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["homicide", "death", "killing", "culpable", "intent to kill"],
        "transition_note": "Replaces IPC 304. Penalty structure similar.",
    },

    # ─── SEXUAL OFFENCES ──────────────────────────────────────────────────────
    {
        "id": "bns_64",
        "section": "BNS Section 64",
        "old_ipc": "IPC Section 376",
        "title": "Punishment for Rape",
        "description": (
            "A man is said to commit 'rape' if he penetrates his penis, or any object "
            "or a part of the body, into the vagina, mouth, urethra or anus of a woman "
            "or makes her do so with him or any other person; or applies his mouth to "
            "the vagina, anus, urethra of a woman or makes her do so, without consent. "
            "Punishment: rigorous imprisonment not less than 10 years, extendable to "
            "life imprisonment + fine."
        ),
        "punishment": "Minimum 10 years rigorous imprisonment, up to life + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["rape", "sexual assault", "penetration", "consent", "victim", "survivor",
                     "woman", "sexual offence", "force", "physical force"],
        "transition_note": "Replaces IPC 376. Minimum sentence clearly stated as 10 years RI.",
    },
    {
        "id": "bns_74",
        "section": "BNS Section 74",
        "old_ipc": "IPC Section 354",
        "title": "Assault or Criminal Force on Woman with Intent to Outrage Her Modesty",
        "description": (
            "Whoever assaults or uses criminal force to any woman, intending to outrage "
            "or knowing it to be likely that he will thereby outrage her modesty, shall "
            "be punished with imprisonment of either description for a term which shall "
            "not be less than one year but which may extend to five years, and shall also "
            "be liable to fine."
        ),
        "punishment": "1 to 5 years imprisonment + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["modesty", "outrage", "assault", "molestation", "groping", "touch",
                     "woman", "sexual harassment", "eve teasing"],
        "transition_note": "Replaces IPC 354. Now explicitly non-bailable with minimum 1 year.",
    },
    {
        "id": "bns_75",
        "section": "BNS Section 75",
        "old_ipc": "IPC Section 354A",
        "title": "Sexual Harassment",
        "description": (
            "A man committing any of the following acts: (i) physical contact and advances "
            "involving unwelcome and explicit sexual overtures; (ii) a demand or request for "
            "sexual favours; (iii) showing pornography against the will of a woman; "
            "(iv) making sexually coloured remarks, shall be guilty of sexual harassment. "
            "Punishment for i, ii, iii: up to 3 years + fine. Punishment for iv: up to 1 year + fine."
        ),
        "punishment": "Up to 3 years + fine (up to 1 year for verbal harassment)",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["sexual harassment", "workplace", "remarks", "overtures", "demand",
                     "pornography", "unwelcome", "advances"],
        "transition_note": "Replaces IPC 354A. Explicitly lists categories of sexual harassment.",
    },
    {
        "id": "bns_77",
        "section": "BNS Section 77",
        "old_ipc": "IPC Section 354C",
        "title": "Voyeurism",
        "description": (
            "Whoever watches, or captures the image of, a woman engaging in a private act "
            "in circumstances where she would usually have the expectation of not being "
            "observed either by the perpetrator or by any other person at the behest of "
            "the perpetrator or disseminates such image, shall be punished. "
            "First conviction: 1–3 years + fine. Second or subsequent: 3–7 years + fine."
        ),
        "punishment": "1-3 years (first), 3-7 years (subsequent) + fine",
        "bailable": "First offence: Bailable. Subsequent: Non-bailable",
        "cognizable": "Yes",
        "keywords": ["voyeurism", "spy camera", "hidden camera", "private act", "video",
                     "photo", "capture", "image", "disseminate", "MMS", "nude"],
        "transition_note": "Replaces IPC 354C. Now explicitly covers dissemination of captured images.",
    },
    {
        "id": "bns_78",
        "section": "BNS Section 78",
        "old_ipc": "IPC Section 354D",
        "title": "Stalking",
        "description": (
            "Any man who follows a woman and contacts, or attempts to contact such woman "
            "to foster personal interaction repeatedly despite a clear indication of "
            "disinterest by such woman; or monitors the use by a woman of the internet, "
            "email or any other form of electronic communication, commits the offence of "
            "stalking. First conviction: up to 3 years. Subsequent: up to 5 years."
        ),
        "punishment": "Up to 3 years (first), up to 5 years (subsequent) + fine",
        "bailable": "First offence: Bailable. Subsequent: Non-bailable",
        "cognizable": "Yes",
        "keywords": ["stalking", "following", "monitor", "cyber stalking", "online harassment",
                     "contact", "repeated", "disinterest", "internet", "social media"],
        "transition_note": "Replaces IPC 354D. Now explicitly includes cyber-stalking via email/internet.",
    },

    # ─── DOWRY & PROPERTY ─────────────────────────────────────────────────────
    {
        "id": "bns_83",
        "section": "BNS Section 83",
        "old_ipc": "IPC Section 498 + Dowry Prohibition Act",
        "title": "Demand for Dowry / Unlawful Demand for Property",
        "description": (
            "This section, read with the Dowry Prohibition Act 1961, penalizes giving, "
            "taking, or demanding dowry. Any demand for property or valuable security from "
            "the woman or her relatives, as a condition of marriage or thereafter, is an "
            "offence. The Dowry Prohibition Act provides for up to 5 years imprisonment "
            "and fine exceeding Rs. 15,000. BNS Section 85 additionally covers the "
            "harassment angle under cruelty."
        ),
        "punishment": "Up to 5 years + fine (Dowry Prohibition Act) + BNS 85 for cruelty",
        "bailable": "Non-bailable (when charged under BNS 85)",
        "cognizable": "Yes",
        "keywords": ["dowry", "demand", "property", "valuables", "gold", "cash",
                     "in-laws", "marriage", "condition", "gifts"],
        "transition_note": "Read with Dowry Prohibition Act 1961. BNS 85 is the primary criminal charge.",
    },

    # ─── KIDNAPPING & ABDUCTION ───────────────────────────────────────────────
    {
        "id": "bns_137",
        "section": "BNS Section 137",
        "old_ipc": "IPC Section 362",
        "title": "Abduction",
        "description": (
            "Whoever by force compels, or by any deceitful means induces any person to "
            "go from any place, is said to abduct that person. This is a core definition "
            "section used with aggravated forms of abduction under BNS 140 (kidnapping for "
            "ransom), BNS 143 (kidnapping to murder), etc."
        ),
        "punishment": "Depends on purpose — up to 7 years, or life imprisonment",
        "bailable": "Non-bailable (in aggravated forms)",
        "cognizable": "Yes",
        "keywords": ["abduction", "kidnap", "force", "deceit", "compel", "take away",
                     "missing person", "ransom", "child", "woman", "trafficking"],
        "transition_note": "Replaces IPC 362. The definition remains the same; aggravated forms are in BNS 140-143.",
    },

    # ─── ASSAULT & BODILY HARM ────────────────────────────────────────────────
    {
        "id": "bns_115",
        "section": "BNS Section 115",
        "old_ipc": "IPC Section 323 / 325",
        "title": "Voluntarily Causing Hurt / Grievous Hurt",
        "description": (
            "BNS 115(1): Whoever voluntarily causes hurt shall be punished with "
            "imprisonment up to 1 year, or fine up to Rs. 10,000, or both. "
            "BNS 115(2): Whoever voluntarily causes grievous hurt (broken bones, permanent "
            "disfigurement, loss of limb, etc.) shall be punished with imprisonment up "
            "to 7 years and fine."
        ),
        "punishment": "Up to 1 year (hurt) or up to 7 years (grievous hurt) + fine",
        "bailable": "Bailable (simple hurt), Non-bailable (grievous hurt)",
        "cognizable": "Yes (grievous hurt), No (simple hurt — compoundable)",
        "keywords": ["assault", "beat", "hit", "attack", "hurt", "injury", "broken bone",
                     "bruise", "wound", "fist", "physical violence", "domestic violence"],
        "transition_note": "Combines IPC 323 (simple hurt) and IPC 325 (grievous hurt) into one section.",
    },

    # ─── CRIMINAL INTIMIDATION & THREATS ─────────────────────────────────────
    {
        "id": "bns_351",
        "section": "BNS Section 351",
        "old_ipc": "IPC Section 503/506",
        "title": "Criminal Intimidation",
        "description": (
            "Whoever threatens another with any injury to his person, reputation or "
            "property, or to the person or reputation of any one in whom that person is "
            "interested, with intent to cause alarm to that person, or to cause that "
            "person to do any act which he is not legally bound to do, or to omit to do "
            "any act which that person is legally entitled to do, as the means of avoiding "
            "the execution of such threat, commits criminal intimidation. "
            "Punishment: Up to 2 years + fine. If threat is death/grievous hurt: up to 7 years."
        ),
        "punishment": "Up to 2 years + fine (or up to 7 years for serious threats)",
        "bailable": "Bailable (simple), Non-bailable (threat of death/grievous hurt)",
        "cognizable": "Yes (serious threats)",
        "keywords": ["threat", "intimidation", "warn", "WhatsApp threat", "verbal threat",
                     "death threat", "scare", "coerce", "blackmail", "message threat"],
        "transition_note": "Replaces IPC 503 and 506. WhatsApp/SMS threats now explicitly covered under cyber provisions.",
    },

    # ─── FRAUD & CHEATING ─────────────────────────────────────────────────────
    {
        "id": "bns_318",
        "section": "BNS Section 318",
        "old_ipc": "IPC Section 420",
        "title": "Cheating and Dishonestly Inducing Delivery of Property",
        "description": (
            "Whoever cheats and thereby dishonestly induces the person deceived to deliver "
            "any property to any person, or to make, alter or destroy the whole or any part "
            "of a valuable security, or anything which is sealed or signed or is capable of "
            "being converted into a valuable security, shall be punished with imprisonment "
            "of either description for a term which may extend to seven years, and shall "
            "also be liable to fine."
        ),
        "punishment": "Up to 7 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["cheating", "fraud", "deceive", "property", "money", "scam",
                     "online fraud", "investment fraud", "false promise", "marriage fraud"],
        "transition_note": "Replaces the famous 'IPC 420'. Same scope, now under BNS 318.",
    },

    # ─── WRONGFUL CONFINEMENT ─────────────────────────────────────────────────
    {
        "id": "bns_126",
        "section": "BNS Section 126",
        "old_ipc": "IPC Section 342/340",
        "title": "Wrongful Confinement / Wrongful Restraint",
        "description": (
            "BNS 126: Wrongful Confinement — Whoever wrongfully restrains any person in "
            "such a manner as to prevent that person from proceeding beyond certain "
            "circumscribing limits, is said wrongfully to confine that person. "
            "Punishment: Up to 1 year + fine or both. Confinement for 3+ days: up to 2 years. "
            "Confinement in secret: up to 3 years."
        ),
        "punishment": "Up to 1-3 years depending on duration + fine",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["locked out", "locked in", "confined", "restrain", "not allowed to leave",
                     "house arrest", "trap", "prevent", "freedom", "movement"],
        "transition_note": "Replaces IPC 340/342. 'Locked her out' or 'kept her confined' directly attracts this section.",
    },

    # ─── CYBERCRIMES ──────────────────────────────────────────────────────────
    {
        "id": "bns_66",
        "section": "BNS Section 66 + IT Act 2000",
        "old_ipc": "IPC Section 509 + IT Act",
        "title": "Word, Gesture or Act Intended to Insult the Modesty of a Woman (Cyber-Enhanced)",
        "description": (
            "BNS Section 79: Whoever, intending to insult the modesty of any woman, "
            "utters any word, makes any sound or gesture, or exhibits any object, intending "
            "that such word or sound shall be heard, or that such gesture or object shall "
            "be seen, by such woman, or intrudes upon the privacy of such woman, shall be "
            "punished with simple imprisonment for a term which may extend to 3 years, "
            "and also with fine. When done via social media/internet, IT Act Sections 66A, "
            "66C, 66E also apply."
        ),
        "punishment": "Up to 3 years + fine + IT Act penalties (up to 3 additional years)",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["social media", "WhatsApp", "Instagram", "Facebook", "cyber harassment",
                     "online abuse", "message", "photo leak", "morphed photo", "insult",
                     "troll", "abuse online", "IT Act", "cyber crime"],
        "transition_note": "BNS 79 replaces IPC 509. Combined with IT Act for cybercrimes targeting women.",
    },

    # ─── MURDER & ATTEMPT ─────────────────────────────────────────────────────
    {
        "id": "bns_103",
        "section": "BNS Section 103",
        "old_ipc": "IPC Section 302",
        "title": "Punishment for Murder",
        "description": (
            "Whoever commits murder shall be punished with death or imprisonment for life "
            "and shall also be liable to fine. Murder is defined as culpable homicide "
            "committed with intent to cause death, or intent to cause such bodily injury "
            "as the offender knows to be likely to cause death, or with knowledge that "
            "the act is imminently dangerous and must cause death."
        ),
        "punishment": "Death or Life Imprisonment + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["murder", "killed", "death", "homicide", "life threat", "extreme violence"],
        "transition_note": "Directly replaces IPC 302. Same punishment — death or life imprisonment.",
    },
    {
        "id": "bns_109",
        "section": "BNS Section 109",
        "old_ipc": "IPC Section 307",
        "title": "Attempt to Murder",
        "description": (
            "Whoever does any act with such intention or knowledge and under such "
            "circumstances that if he by that act caused death he would be guilty of murder, "
            "shall be punished with imprisonment of either description for a term which may "
            "extend to ten years, and shall also be liable to fine. If hurt is caused: "
            "imprisonment for life or rigorous imprisonment up to 10 years."
        ),
        "punishment": "Up to 10 years + fine; if hurt caused: Life imprisonment",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["attempt murder", "tried to kill", "life threatening attack",
                     "weapon", "knife", "gun", "acid attack attempt"],
        "transition_note": "Replaces IPC 307. Same scope. Applied when murder is attempted but victim survives.",
    },

    # ─── DEFAMATION ───────────────────────────────────────────────────────────
    {
        "id": "bns_356",
        "section": "BNS Section 356",
        "old_ipc": "IPC Section 499/500",
        "title": "Defamation",
        "description": (
            "Whoever, by words either spoken or intended to be read, or by signs or by "
            "visible representations, makes or publishes any imputation concerning any "
            "person intending to harm, or knowing or having reason to believe that such "
            "imputation will harm, the reputation of such person, is said to defame that "
            "person. Punishment: Simple imprisonment up to 2 years, or fine, or both."
        ),
        "punishment": "Up to 2 years simple imprisonment + fine",
        "bailable": "Bailable",
        "cognizable": "Non-cognizable (private complaint required)",
        "keywords": ["defamation", "slander", "libel", "reputation", "false statement",
                     "social media defamation", "fake news", "imputation", "character assassination"],
        "transition_note": "Replaces IPC 499/500. Defamation is still bailable and non-cognizable — requires a private complaint in Magistrate court.",
    },
]


def get_all_documents():
    """Returns a list of text strings and metadata for ChromaDB ingestion."""
    documents = []
    metadatas = []
    ids = []

    for section in BNS_SECTIONS:
        # Build a rich text document combining all fields for semantic search
        doc_text = (
            f"{section['section']} | Previously: {section['old_ipc']}\n"
            f"TITLE: {section['title']}\n"
            f"DESCRIPTION: {section['description']}\n"
            f"PUNISHMENT: {section['punishment']}\n"
            f"BAILABLE STATUS: {section['bailable']}\n"
            f"COGNIZABLE: {section['cognizable']}\n"
            f"KEYWORDS: {', '.join(section['keywords'])}\n"
            f"TRANSITION NOTE: {section['transition_note']}"
        )

        meta = {
            "section": section["section"],
            "old_ipc": section["old_ipc"],
            "title": section["title"],
            "punishment": section["punishment"],
            "bailable": section["bailable"],
            "cognizable": section["cognizable"],
            "transition_note": section["transition_note"],
        }

        documents.append(doc_text)
        metadatas.append(meta)
        ids.append(section["id"])

    return documents, metadatas, ids
