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

    # ─── HOMICIDE — DEFINITIONS & NEGLIGENT DEATH ─────────────────────────────
    {
        "id": "bns_100",
        "section": "BNS Section 100",
        "old_ipc": "IPC Section 299",
        "title": "Culpable Homicide (Definition)",
        "description": (
            "Whoever causes death by doing an act with the intention of causing death, or "
            "with the intention of causing such bodily injury as is likely to cause death, "
            "or with the knowledge that he is likely by such act to cause death, commits the "
            "offence of culpable homicide. This is the foundational definition; the punishment "
            "is found in BNS 105 (culpable homicide not amounting to murder) or BNS 103 "
            "(when it amounts to murder)."
        ),
        "punishment": "Definition section — see BNS 103 (murder) or BNS 105 (CHnoM)",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["culpable homicide", "definition", "intent", "knowledge", "death", "killing"],
        "transition_note": "Replaces IPC 299. Foundational definition used to distinguish murder from CHnoM.",
    },
    {
        "id": "bns_101",
        "section": "BNS Section 101",
        "old_ipc": "IPC Section 300",
        "title": "Murder (Definition)",
        "description": (
            "Culpable homicide is murder if the act causing death is done with the intention "
            "of causing death; or with the intention of causing such bodily injury as the "
            "offender knows to be likely to cause the death of the person; or with the intention "
            "of causing bodily injury sufficient in the ordinary course of nature to cause death; "
            "or if the person committing the act knows it to be so imminently dangerous that it "
            "must in all probability cause death. Exceptions: grave and sudden provocation, "
            "private defence exceeded in good faith, public servant exceeding power in good "
            "faith, sudden fight without premeditation, consent of the deceased (over 18)."
        ),
        "punishment": "See BNS 103 for the punishment for murder",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["murder", "definition", "intent", "imminently dangerous", "exceptions",
                     "provocation", "private defence", "sudden fight"],
        "transition_note": "Replaces IPC 300. The five 'exceptions' to murder remain unchanged.",
    },
    {
        "id": "bns_106",
        "section": "BNS Section 106",
        "old_ipc": "IPC Section 304A",
        "title": "Causing Death by Negligence",
        "description": (
            "Whoever causes the death of any person by doing any rash or negligent act not "
            "amounting to culpable homicide, shall be punished with imprisonment of either "
            "description for a term which may extend to five years, and shall also be liable "
            "to fine. BNS 106(2) — where the death is caused by a registered medical "
            "practitioner while performing a medical procedure: imprisonment up to 2 years and "
            "fine. NOTE: The hit-and-run sub-section (originally proposed at 10 years) has been "
            "kept in abeyance by the Government of India pending consultations."
        ),
        "punishment": "Up to 5 years + fine (medical practitioner: up to 2 years + fine)",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["road accident", "negligence", "rash driving", "hit and run", "medical negligence",
                     "doctor", "death by accident", "industrial accident", "motor vehicle"],
        "transition_note": "Replaces IPC 304A. The sentence for non-medical negligence increased from 2 years (IPC) to 5 years (BNS).",
    },
    {
        "id": "bns_105",
        "section": "BNS Section 105",
        "old_ipc": "IPC Section 304",
        "title": "Punishment for Culpable Homicide not Amounting to Murder",
        "description": (
            "Whoever commits culpable homicide not amounting to murder shall be punished with "
            "imprisonment for life, or imprisonment of either description for a term which may "
            "extend to ten years, and shall also be liable to fine, if the act by which the "
            "death is caused is done with the intention of causing death, or of causing such "
            "bodily injury as is likely to cause death; or with imprisonment of either "
            "description for a term which may extend to ten years, or with fine, or with both, "
            "if the act is done with the knowledge that it is likely to cause death, but "
            "without any intention to cause death, or to cause such bodily injury as is likely "
            "to cause death."
        ),
        "punishment": "Life imprisonment or up to 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["culpable homicide not amounting to murder", "CHnoM", "manslaughter",
                     "sudden fight", "provocation", "death without intent"],
        "transition_note": "Replaces IPC 304. Note: BNS 80 in the existing KB referred to this; the official numbering is 105.",
    },

    # ─── ORGANISED CRIME, TERROR, MOB LYNCHING (NEW IN BNS) ───────────────────
    {
        "id": "bns_111",
        "section": "BNS Section 111",
        "old_ipc": "(NEW — no direct IPC equivalent, partially covered by MCOCA/UAPA)",
        "title": "Organised Crime",
        "description": (
            "Any continuing unlawful activity including kidnapping, robbery, vehicle theft, "
            "extortion, land grabbing, contract killing, economic offences, cyber-crimes, "
            "trafficking of persons, drugs, weapons or illicit goods or services, human "
            "trafficking, prostitution or ransom, by any person or a group of persons acting "
            "in concert, singly or jointly, either as a member of an organised crime syndicate "
            "or on behalf of such syndicate, by use of violence, threat of violence, "
            "intimidation, coercion, or by any other unlawful means to obtain direct or "
            "indirect material benefit including a financial benefit, shall constitute "
            "organised crime. If such an offence results in the death of any person — death "
            "or imprisonment for life and fine of not less than ten lakh rupees. In other "
            "cases — imprisonment for not less than five years extendable to life and fine "
            "of not less than five lakh rupees."
        ),
        "punishment": "Death/Life + ₹10 lakh fine (if death); else 5 years to life + ₹5 lakh fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["organised crime", "syndicate", "gang", "extortion", "land grabbing",
                     "contract killing", "trafficking", "ransom", "mafia", "MCOCA", "underworld"],
        "transition_note": "NEW provision in BNS — there was no parallel section in IPC. Brings MCOCA-style charging into the general criminal code.",
    },
    {
        "id": "bns_113",
        "section": "BNS Section 113",
        "old_ipc": "(NEW in BNS — partial overlap with UAPA)",
        "title": "Terrorist Act",
        "description": (
            "Whoever does any act with the intent to threaten or likely to threaten the unity, "
            "integrity, sovereignty, security, or economic security of India or with the intent "
            "to strike terror or likely to strike terror in the people or any section of the "
            "people in India or in any foreign country, by using bombs, dynamite, explosive "
            "substances, biological/radiological/nuclear substances, or by causing death, "
            "damage to property, disruption of essential supplies/services, or counterfeit "
            "currency, commits a terrorist act. Punishment: Death or imprisonment for life if "
            "death results; otherwise not less than five years extendable to life. Conspiracy "
            "or recruitment for a terrorist act is also punishable."
        ),
        "punishment": "Death/Life if death results; else minimum 5 years to Life + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["terrorism", "terror", "bomb", "explosive", "national security",
                     "sovereignty", "UAPA", "conspiracy", "recruitment", "biological weapon"],
        "transition_note": "NEW in BNS — UAPA continues to operate, but BNS 113 brings terrorism charging into the general criminal code.",
    },
    {
        "id": "bns_103_2",
        "section": "BNS Section 103(2)",
        "old_ipc": "(NEW — mob lynching specific)",
        "title": "Murder by Group / Mob Lynching",
        "description": (
            "When a group of five or more persons acting in concert commits murder on the "
            "ground of race, caste or community, sex, place of birth, language, personal "
            "belief or any other similar ground, each member of such group shall be punished "
            "with death or with imprisonment for life, and shall also be liable to fine. This "
            "sub-section was specifically added to address mob lynching incidents, addressing "
            "the gap previously identified by the Supreme Court in Tehseen Poonawalla v. UoI "
            "(2018)."
        ),
        "punishment": "Death or Life Imprisonment + fine (each member of the mob)",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["mob lynching", "lynching", "group murder", "communal violence", "hate crime",
                     "five or more persons", "caste violence", "religious violence"],
        "transition_note": "NEW provision in BNS — IPC had no specific mob lynching section. Implements the Tehseen Poonawalla (2018) Supreme Court directive.",
    },

    # ─── KIDNAPPING FOR RANSOM, TRAFFICKING ───────────────────────────────────
    {
        "id": "bns_140",
        "section": "BNS Section 140",
        "old_ipc": "IPC Section 364A",
        "title": "Kidnapping for Ransom etc.",
        "description": (
            "Whoever kidnaps or abducts any person and keeps such person in detention and "
            "threatens to cause death or hurt to such person, in order to compel the "
            "Government, foreign State, international/inter-governmental organisation, or any "
            "other person, to do or abstain from doing any act, or to pay a ransom, shall be "
            "punishable with death, or imprisonment for life, and shall also be liable to fine."
        ),
        "punishment": "Death or Life Imprisonment + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["kidnap for ransom", "abduction for ransom", "hostage", "ransom",
                     "extort", "child kidnap", "demand money"],
        "transition_note": "Replaces IPC 364A. Same scope — death or life imprisonment for ransom kidnapping.",
    },
    {
        "id": "bns_143",
        "section": "BNS Section 143",
        "old_ipc": "IPC Section 370",
        "title": "Trafficking of Persons",
        "description": (
            "Whoever, for the purpose of exploitation, recruits, transports, harbours, "
            "transfers, or receives a person, by using threats, force, coercion, abduction, "
            "fraud, deception, abuse of power, or by inducement, including the giving or "
            "receiving of payments to achieve the consent of any person having control over "
            "the person recruited, commits the offence of trafficking. Exploitation includes "
            "any act of physical exploitation or any form of sexual exploitation, slavery, "
            "servitude, or the forced removal of organs. Punishment: 7-10 years + fine; "
            "trafficking of more than one person: 10 years to life + fine; trafficking of a "
            "minor: 10 years to life + fine."
        ),
        "punishment": "7-10 years (single victim); 10 years to life (multiple/minor) + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["human trafficking", "slavery", "forced labour", "sex trafficking",
                     "minor trafficking", "organ trade", "bonded labour", "exploitation"],
        "transition_note": "Replaces IPC 370. Definition of 'exploitation' is broader, explicitly includes organ removal.",
    },

    # ─── THEFT, ROBBERY, DACOITY, SNATCHING ───────────────────────────────────
    {
        "id": "bns_303",
        "section": "BNS Section 303",
        "old_ipc": "IPC Section 378/379",
        "title": "Theft",
        "description": (
            "Whoever, intending to take dishonestly any movable property out of the "
            "possession of any person without that person's consent, moves that property in "
            "order to such taking, is said to commit theft. Punishment: imprisonment of either "
            "description for a term which may extend to three years, or with fine, or with "
            "both. For repeat offenders (second or subsequent conviction): minimum one year "
            "rigorous imprisonment, extendable to five years + fine."
        ),
        "punishment": "Up to 3 years + fine; repeat offender: 1-5 years RI + fine",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["theft", "stolen", "dishonestly took", "movable property", "shoplifting",
                     "pickpocket", "stealing", "missing property"],
        "transition_note": "Replaces IPC 378/379. Repeat-offender enhancement is new in BNS.",
    },
    {
        "id": "bns_304",
        "section": "BNS Section 304",
        "old_ipc": "(NEW — no direct IPC equivalent)",
        "title": "Snatching",
        "description": (
            "Theft is 'snatching' if, in order to commit theft, the offender suddenly or "
            "quickly or forcibly seizes, secures, grabs, or takes away from any person or from "
            "his possession any movable property. Punishment: imprisonment of either "
            "description for a term which may extend to three years, and shall also be liable "
            "to fine. This recognises chain-snatching and phone-snatching as distinct, faster-"
            "to-charge offences than robbery."
        ),
        "punishment": "Up to 3 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["snatching", "chain snatching", "phone snatching", "purse snatching",
                     "grab", "seize", "sudden taking", "street crime"],
        "transition_note": "NEW provision in BNS — IPC had no specific snatching offence (was usually charged under theft or robbery).",
    },
    {
        "id": "bns_309",
        "section": "BNS Section 309",
        "old_ipc": "IPC Section 390/392",
        "title": "Robbery",
        "description": (
            "In all robbery there is either theft or extortion. Theft is robbery if, in order "
            "to the committing of the theft, or in committing the theft, or in carrying away "
            "or attempting to carry away property obtained by the theft, the offender, for "
            "that end, voluntarily causes or attempts to cause to any person death or hurt or "
            "wrongful restraint, or fear of instant death or instant hurt, or instant wrongful "
            "restraint. Punishment: rigorous imprisonment for a term which may extend to ten "
            "years, and shall also be liable to fine. Robbery on the highway between sunset "
            "and sunrise: minimum 14 years."
        ),
        "punishment": "Up to 10 years RI + fine; highway robbery at night: 14 years to life",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["robbery", "armed robbery", "loot", "force", "weapon", "violent theft",
                     "highway robbery", "armed", "knife", "gun"],
        "transition_note": "Replaces IPC 390/392. Highway-robbery enhancement (14 years) preserved.",
    },
    {
        "id": "bns_310",
        "section": "BNS Section 310",
        "old_ipc": "IPC Section 391/395/396",
        "title": "Dacoity",
        "description": (
            "When five or more persons conjointly commit or attempt to commit a robbery, or "
            "where the whole number of persons conjointly committing or attempting to commit "
            "a robbery, and persons present and aiding such commission or attempt, amount to "
            "five or more, every person so committing, attempting or aiding, is said to "
            "commit dacoity. Punishment: imprisonment for life, or rigorous imprisonment for a "
            "term which may extend to ten years, and shall also be liable to fine. Dacoity "
            "with murder: death, life imprisonment, or rigorous imprisonment up to 10 years + "
            "fine."
        ),
        "punishment": "Life or up to 10 years RI + fine; with murder: Death/Life + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["dacoity", "five or more", "armed gang", "village robbery", "mass robbery",
                     "gang", "loot", "armed group"],
        "transition_note": "Replaces IPC 391/395/396. The 'five or more persons' threshold remains.",
    },

    # ─── BREACH OF TRUST, FORGERY ─────────────────────────────────────────────
    {
        "id": "bns_316",
        "section": "BNS Section 316",
        "old_ipc": "IPC Section 405/406",
        "title": "Criminal Breach of Trust",
        "description": (
            "Whoever, being in any manner entrusted with property, or with any dominion over "
            "property, dishonestly misappropriates or converts to his own use that property, "
            "or dishonestly uses or disposes of that property in violation of any direction "
            "of law prescribing the mode in which such trust is to be discharged, or of any "
            "legal contract, express or implied, which he has made touching the discharge of "
            "such trust, or wilfully suffers any other person so to do, commits criminal "
            "breach of trust. Punishment: imprisonment of either description up to five years, "
            "or fine, or both. Aggravated forms (by clerk/servant/banker/public servant) carry "
            "higher punishments up to life imprisonment."
        ),
        "punishment": "Up to 5 years + fine; aggravated: up to 10 years to Life + fine",
        "bailable": "Non-bailable (aggravated)",
        "cognizable": "Yes",
        "keywords": ["breach of trust", "misappropriation", "embezzlement", "employee fraud",
                     "trustee", "public servant fraud", "company fraud", "fiduciary"],
        "transition_note": "Replaces IPC 405/406. Aggravated forms (clerk/servant/banker) remain in subsequent sub-sections.",
    },
    {
        "id": "bns_336",
        "section": "BNS Section 336",
        "old_ipc": "IPC Section 463/465",
        "title": "Forgery",
        "description": (
            "Whoever makes any false document or false electronic record or part of a "
            "document or electronic record, with intent to cause damage or injury to the "
            "public or to any person, or to support any claim or title, or to cause any person "
            "to part with property, or to enter into any express or implied contract, or with "
            "intent to commit fraud or that fraud may be committed, commits forgery. "
            "Punishment for forgery: imprisonment of either description up to two years, or "
            "fine, or both. Forgery for cheating purposes: up to 7 years + fine. Forgery of "
            "valuable security/will: up to 10 years + fine."
        ),
        "punishment": "Up to 2 years + fine; for cheating: up to 7 years; valuable security: up to 10 years",
        "bailable": "Bailable (simple forgery)",
        "cognizable": "Yes",
        "keywords": ["forgery", "fake document", "fake signature", "fake will", "fake cheque",
                     "forged", "false document", "fake electronic record", "fake stamp"],
        "transition_note": "Replaces IPC 463/465. Now explicitly includes 'false electronic record' — covers digital forgery.",
    },

    # ─── PROMOTING ENMITY, RIOTING, UNLAWFUL ASSEMBLY ─────────────────────────
    {
        "id": "bns_191",
        "section": "BNS Section 191",
        "old_ipc": "IPC Section 146/147",
        "title": "Rioting",
        "description": (
            "Whenever force or violence is used by an unlawful assembly, or by any member "
            "thereof, in prosecution of the common object of such assembly, every member of "
            "such assembly is guilty of the offence of rioting. Punishment: imprisonment of "
            "either description for a term which may extend to two years, or with fine, or "
            "with both. Rioting armed with deadly weapon: up to five years + fine."
        ),
        "punishment": "Up to 2 years + fine; armed: up to 5 years + fine",
        "bailable": "Bailable; armed rioting: Non-bailable",
        "cognizable": "Yes",
        "keywords": ["riot", "rioting", "unlawful assembly", "mob", "violence", "communal riot",
                     "weapons", "stone pelting", "crowd violence"],
        "transition_note": "Replaces IPC 146/147. Five-or-more threshold for unlawful assembly preserved.",
    },
    {
        "id": "bns_196",
        "section": "BNS Section 196",
        "old_ipc": "IPC Section 153A",
        "title": "Promoting Enmity Between Groups",
        "description": (
            "Whoever, by words either spoken or written, or by signs or by visible "
            "representations or otherwise, promotes or attempts to promote, on grounds of "
            "religion, race, place of birth, residence, language, caste or community or any "
            "other ground whatsoever, disharmony or feelings of enmity, hatred or ill-will "
            "between different religious, racial, language or regional groups or castes or "
            "communities, or commits any act which is prejudicial to the maintenance of "
            "harmony between such groups, shall be punished with imprisonment of either "
            "description for a term which may extend to three years, or with fine, or with "
            "both. If committed in a place of worship: up to 5 years + fine."
        ),
        "punishment": "Up to 3 years + fine; in place of worship: up to 5 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["hate speech", "promoting enmity", "communal", "religious hatred",
                     "caste hatred", "incite", "social media hate", "viral video", "incitement"],
        "transition_note": "Replaces IPC 153A. Explicitly includes 'visible representations' — covers viral images/videos.",
    },

    # ─── ABETMENT, ATTEMPT, CRIMINAL CONSPIRACY ───────────────────────────────
    {
        "id": "bns_45",
        "section": "BNS Section 45",
        "old_ipc": "IPC Section 107",
        "title": "Abetment (Definition)",
        "description": (
            "A person abets the doing of a thing who: (i) instigates any person to do that "
            "thing; or (ii) engages with one or more other persons in any conspiracy for the "
            "doing of that thing, if an act or illegal omission takes place in pursuance of "
            "that conspiracy, and in order to the doing of that thing; or (iii) intentionally "
            "aids, by any act or illegal omission, the doing of that thing. The punishment "
            "for abetment is provided in subsequent sections (BNS 49–55), and in most cases "
            "is the same as the punishment for the offence abetted."
        ),
        "punishment": "Generally same as the offence abetted (see BNS 49-55)",
        "bailable": "Depends on the offence abetted",
        "cognizable": "Depends on the offence abetted",
        "keywords": ["abetment", "instigate", "aid", "conspiracy", "encouragement",
                     "facilitate crime", "help in crime", "abettor"],
        "transition_note": "Replaces IPC 107. Definition is identical; punishments are now consolidated in BNS 49-55.",
    },
    {
        "id": "bns_61",
        "section": "BNS Section 61",
        "old_ipc": "IPC Section 120A/120B",
        "title": "Criminal Conspiracy",
        "description": (
            "When two or more persons agree to do, or cause to be done — (a) an illegal act, "
            "or (b) an act which is not illegal by illegal means — such an agreement is "
            "designated a criminal conspiracy. Punishment: where the conspiracy is for an "
            "offence punishable with death, life imprisonment or rigorous imprisonment for a "
            "term of two years or more — same punishment as if the person had abetted such "
            "offence. In any other case — imprisonment up to six months, or fine, or both."
        ),
        "punishment": "Same as offence (if serious); else up to 6 months + fine",
        "bailable": "Depends on the underlying offence",
        "cognizable": "Depends on the underlying offence",
        "keywords": ["conspiracy", "agreement to commit crime", "plotting", "joint plan",
                     "two or more persons", "criminal conspiracy"],
        "transition_note": "Replaces IPC 120A/120B. Definition unchanged.",
    },

    # ─── DRUNK DRIVING / NEGLIGENT ACT (PUBLIC SAFETY) ────────────────────────
    {
        "id": "bns_125",
        "section": "BNS Section 125",
        "old_ipc": "IPC Section 336/337/338",
        "title": "Act Endangering Life or Personal Safety of Others",
        "description": (
            "Whoever does any act so rashly or negligently as to endanger human life or the "
            "personal safety of others — punishable with imprisonment up to three months, or "
            "fine up to ₹2,500, or both. If hurt is caused: up to 6 months or fine up to "
            "₹5,000, or both. If grievous hurt is caused: up to 3 years, or fine up to "
            "₹10,000, or both."
        ),
        "punishment": "Up to 3 months / 6 months / 3 years depending on outcome + fine",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["rash driving", "negligent driving", "drunk driving", "endangering life",
                     "public safety", "factory accident", "construction accident"],
        "transition_note": "Consolidates IPC 336/337/338. Fines have been increased substantially.",
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
