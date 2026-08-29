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
        "id": "bns_80",
        "section": "BNS Section 80",
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
        "transition_note": (
            "Replaces IPC 304B. Minimum sentence is 7 years. Presumption of guilt on accused. "
            "NOTE: dowry death is BNS 80 (NOT 84 — BNS 84 is enticing a married woman)."
        ),
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
        # Demand for dowry is punished by the Dowry Prohibition Act, not a BNS
        # section — the section field deliberately carries no BNS number so the
        # verifier never vouches for a fake one. (The old entry mislabelled
        # this as "BNS 83", which is actually fraudulent marriage ceremony.)
        "id": "dpa_dowry_demand",
        "section": "Dowry Prohibition Act — demanding dowry",
        "old_ipc": "Dowry Prohibition Act 1961 (unchanged by BNS)",
        "title": "Demand for Dowry / Unlawful Demand for Property (DP Act Ss. 3-4)",
        "description": (
            "Demanding dowry is punished under the Dowry Prohibition Act 1961, which "
            "remains in force alongside the BNS. Section 3 (taking/giving dowry): "
            "imprisonment of minimum 5 years and fine of Rs 15,000 or the value of the "
            "dowry, whichever is more. Section 4 (demanding dowry): 6 months to 2 years "
            "and fine up to Rs 10,000. Any demand for property or valuable security from "
            "the woman or her relatives, as a condition of marriage or thereafter, is an "
            "offence. BNS Section 85 additionally covers the harassment angle under "
            "cruelty, and dowry death is BNS Section 80."
        ),
        "punishment": "DP Act S.3: min 5 years + fine; S.4: 6 months-2 years + fine; plus BNS 85 for cruelty",
        "bailable": "Non-bailable (when charged under BNS 85)",
        "cognizable": "Yes",
        "keywords": ["dowry", "demand", "property", "valuables", "gold", "cash",
                     "in-laws", "marriage", "condition", "gifts"],
        "transition_note": "Read with Dowry Prohibition Act 1961. BNS 85 is the primary criminal charge.",
    },

    # ─── KIDNAPPING & ABDUCTION ───────────────────────────────────────────────
    {
        "id": "bns_138",
        "section": "BNS Section 138",
        "old_ipc": "IPC Section 362",
        "title": "Abduction",
        "description": (
            "Whoever by force compels, or by any deceitful means induces any person to "
            "go from any place, is said to abduct that person. This is a core definition "
            "section used with aggravated forms under BNS 140 (kidnapping or abducting in "
            "order to murder or for ransom). Kidnapping itself is BNS Section 137."
        ),
        "punishment": "Depends on purpose — up to 7 years, or life imprisonment (aggravated forms)",
        "bailable": "Non-bailable (in aggravated forms)",
        "cognizable": "Yes",
        "keywords": ["abduction", "kidnap", "force", "deceit", "compel", "take away",
                     "missing person", "ransom", "child", "woman", "trafficking"],
        "transition_note": (
            "Replaces IPC 362. NOTE: abduction is BNS 138; kidnapping is BNS 137 "
            "(the old entry had these swapped). Aggravated forms are BNS 139-144."
        ),
    },

    # ─── ASSAULT & BODILY HARM ────────────────────────────────────────────────
    {
        "id": "bns_115",
        "section": "BNS Section 115",
        "old_ipc": "IPC Section 323",
        "title": "Voluntarily Causing Hurt",
        "description": (
            "Whoever voluntarily causes hurt shall be punished with imprisonment up to "
            "1 year, or fine up to Rs. 10,000, or both. 'Hurt' means bodily pain, "
            "disease or infirmity (BNS 114). For grievous hurt (broken bones, permanent "
            "disfigurement, loss of limb, etc.) see BNS Section 117."
        ),
        "punishment": "Up to 1 year, or fine up to Rs 10,000, or both",
        "bailable": "Bailable",
        "cognizable": "No (simple hurt — compoundable)",
        "keywords": ["assault", "beat", "hit", "attack", "hurt", "injury",
                     "bruise", "wound", "fist", "physical violence", "domestic violence"],
        "transition_note": (
            "Replaces IPC 323. NOTE: grievous hurt is a separate section — BNS 117 "
            "(the old entry wrongly folded it into 115)."
        ),
    },
    {
        "id": "bns_117",
        "section": "BNS Section 117",
        "old_ipc": "IPC Section 325",
        "title": "Voluntarily Causing Grievous Hurt",
        "description": (
            "Whoever voluntarily causes grievous hurt shall be punished with "
            "imprisonment up to 7 years and fine. 'Grievous hurt' (BNS 116) includes "
            "emasculation, permanent loss of sight or hearing, loss of a limb or joint, "
            "permanent disfiguration of the head or face, fracture or dislocation of a "
            "bone or tooth, and any hurt which endangers life or keeps the victim in "
            "severe bodily pain or unable to follow ordinary pursuits for 15 days."
        ),
        "punishment": "Up to 7 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["grievous hurt", "broken bone", "fracture", "disfigurement",
                     "loss of limb", "serious injury", "attack", "assault", "beat"],
        "transition_note": "Replaces IPC 325. Definition of grievous hurt is BNS 116.",
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
        "id": "bns_127",
        "section": "BNS Section 127",
        "old_ipc": "IPC Section 340/342",
        "title": "Wrongful Confinement",
        "description": (
            "Whoever wrongfully restrains any person in such a manner as to prevent "
            "that person from proceeding beyond certain circumscribing limits, is said "
            "wrongfully to confine that person. Punishment: up to 1 year + fine or both. "
            "Confinement for 3+ days: up to 3 years. Confinement in secret: up to 3 "
            "years. Wrongful restraint (merely obstructing movement) is the lighter "
            "offence under BNS Section 126."
        ),
        "punishment": "Up to 1-3 years depending on duration + fine",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["locked out", "locked in", "confined", "restrain", "not allowed to leave",
                     "house arrest", "trap", "prevent", "freedom", "movement"],
        "transition_note": (
            "Replaces IPC 340/342. NOTE: confinement is BNS 127; restraint is BNS 126 "
            "(the old entry put confinement under 126). 'Locked her in' attracts 127."
        ),
    },

    # ─── CYBERCRIMES ──────────────────────────────────────────────────────────
    {
        "id": "bns_79",
        "section": "BNS Section 79",
        "old_ipc": "IPC Section 509 + IT Act",
        "title": "Word, Gesture or Act Intended to Insult the Modesty of a Woman (Cyber-Enhanced)",
        "description": (
            "Whoever, intending to insult the modesty of any woman, utters any word, "
            "makes any sound or gesture, or exhibits any object, intending that such "
            "word or sound shall be heard, or that such gesture or object shall be "
            "seen, by such woman, or intrudes upon the privacy of such woman, shall be "
            "punished with simple imprisonment for a term which may extend to 3 years, "
            "and also with fine. When done via social media/internet, IT Act Sections "
            "66C (identity theft), 66E (privacy violation) and 67 (obscene material) "
            "may also apply. (IT Act 66A was struck down in Shreya Singhal v. Union of "
            "India (2015) — never cite it.)"
        ),
        "punishment": "Up to 3 years + fine + IT Act penalties where applicable",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["social media", "WhatsApp", "Instagram", "Facebook", "cyber harassment",
                     "online abuse", "message", "photo leak", "morphed photo", "insult",
                     "troll", "abuse online", "IT Act", "cyber crime"],
        "transition_note": (
            "BNS 79 replaces IPC 509 (the old entry mislabelled this as BNS 66, which "
            "is punishment for rape causing death/vegetative state). Combined with IT "
            "Act for cybercrimes targeting women."
        ),
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

    # ═══ v1.9 Week-2 expansion — section numbers/titles verified against the
    # devgan.in BNS chapter indexes; punishments for new/changed provisions
    # verified against the per-section pages (fetched 2026-07-20). ═══
    {
        "id": "bns_63",
        "section": "BNS Section 63",
        "old_ipc": "IPC Section 375",
        "title": "Rape (Definition)",
        "description": "Defines rape: penetration or manipulation without consent, against her will, with consent obtained by fear/fraud, when she is unable to communicate consent, or when she is under eighteen years of age. Consent must be an unequivocal voluntary agreement. Exception 2 (sexual acts by a husband with his wife not under eighteen) remains subject to pending constitutional challenge on marital rape.",
        "punishment": "Definition section \u2014 punishments in BNS 64-70",
        "bailable": "N/A (definition)",
        "cognizable": "N/A (definition)",
        "keywords": ["rape", "consent", "definition", "sexual assault", "against will", "minor"],
        "transition_note": "Replaces IPC 375. Punishments are in BNS 64 (basic), 65 (minors), 66 (death/vegetative state), 70 (gang rape).",
    },
    {
        "id": "bns_65",
        "section": "BNS Section 65",
        "old_ipc": "IPC Section 376AB / 376DA / 376DB",
        "title": "Punishment for Rape of Woman Under Sixteen / Under Twelve",
        "description": "Rape of a woman under sixteen years of age: rigorous imprisonment of minimum twenty years, extendable to imprisonment for life (meaning the remainder of natural life) and fine. Rape of a woman under twelve years: minimum twenty years to life (natural life), and fine, or death. Fine must be just and reasonable to meet medical expenses and rehabilitation, paid to the victim.",
        "punishment": "Under 16: min 20 years to life + fine; under 12: min 20 years to life, or death",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["rape", "minor", "child", "under sixteen", "under twelve", "POCSO", "death penalty"],
        "transition_note": "Consolidates IPC child-rape provisions. POCSO Act applies in parallel for victims under 18.",
    },
    {
        "id": "bns_69",
        "section": "BNS Section 69",
        "old_ipc": "New provision (no direct IPC equivalent)",
        "title": "Sexual Intercourse by Employing Deceitful Means, etc.",
        "description": "Whoever, by deceitful means or by making a promise to marry a woman without any intention of fulfilling it, has sexual intercourse with her (such intercourse not amounting to rape) shall be punished. 'Deceitful means' includes inducement of false promise of employment or promotion, or marrying after suppressing identity.",
        "punishment": "Up to 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["false promise of marriage", "deceit", "consent", "live-in", "breach of promise", "suppressed identity", "employment promise"],
        "transition_note": "NEW in BNS \u2014 the 'false promise to marry' line of cases is now a distinct statutory offence.",
    },
    {
        "id": "bns_70",
        "section": "BNS Section 70",
        "old_ipc": "IPC Section 376D",
        "title": "Gang Rape",
        "description": "Where a woman is raped by one or more persons constituting a group or acting in furtherance of a common intention, each person is deemed to have committed rape: rigorous imprisonment of minimum twenty years, extendable to life (remainder of natural life), and fine payable to the victim. Where the victim is under eighteen years (70(2)): imprisonment for life (natural life) and fine, or death.",
        "punishment": "Min 20 years to life + fine to victim; victim under 18: life (natural life) or death",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["gang rape", "group", "common intention", "multiple accused", "death penalty"],
        "transition_note": "Replaces IPC 376D/376DA. Each member of the group is deemed to have committed rape.",
    },
    {
        "id": "bns_72",
        "section": "BNS Section 72",
        "old_ipc": "IPC Section 228A",
        "title": "Disclosure of Identity of Victim of Certain Offences",
        "description": "Whoever prints or publishes the name or any matter which may make known the identity of a victim of offences under BNS 64-71 (rape and allied offences) shall be punished. Applies to media, social media posts, and court reporting without permission.",
        "punishment": "Up to 2 years + fine",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["victim identity", "media", "publication", "privacy", "rape victim", "social media", "name disclosure"],
        "transition_note": "Replaces IPC 228A. Sharing a victim's name on WhatsApp/social media attracts this section.",
    },
    {
        "id": "bns_76",
        "section": "BNS Section 76",
        "old_ipc": "IPC Section 354B",
        "title": "Assault or Use of Criminal Force to Woman with Intent to Disrobe",
        "description": "Whoever assaults or uses criminal force to any woman, or abets such act, with the intention of disrobing or compelling her to be naked, shall be punished with imprisonment of minimum three years extendable to seven years, and fine.",
        "punishment": "3 to 7 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["disrobe", "strip", "assault", "criminal force", "modesty", "naked", "public humiliation"],
        "transition_note": "Replaces IPC 354B. Minimum sentence of 3 years.",
    },
    {
        "id": "bns_82",
        "section": "BNS Section 82",
        "old_ipc": "IPC Section 494/495",
        "title": "Marrying Again During Lifetime of Husband or Wife (Bigamy)",
        "description": "Whoever, having a husband or wife living, marries again in any case in which such marriage is void by reason of its taking place during the life of such husband or wife: up to seven years and fine. If the former marriage was concealed from the person with whom the subsequent marriage is contracted: up to ten years and fine (82(2)).",
        "punishment": "Up to 7 years + fine; with concealment: up to 10 years + fine",
        "bailable": "Bailable",
        "cognizable": "No (complaint by aggrieved person)",
        "keywords": ["bigamy", "second marriage", "spouse living", "void marriage", "concealment"],
        "transition_note": "Replaces IPC 494/495. Non-cognizable \u2014 proceeds on complaint of the aggrieved spouse.",
    },
    {
        "id": "bns_86",
        "section": "BNS Section 86",
        "old_ipc": "IPC Section 498A (Explanation)",
        "title": "Cruelty Defined (for BNS 85)",
        "description": "'Cruelty' for the purpose of BNS 85 means: (a) any wilful conduct of such a nature as is likely to drive the woman to commit suicide or to cause grave injury or danger to life, limb or health (mental or physical); or (b) harassment of the woman to coerce her or any person related to her to meet any unlawful demand for property or valuable security, or on account of failure to meet such demand.",
        "punishment": "Definition section \u2014 punishment is under BNS 85 (up to 3 years + fine)",
        "bailable": "N/A (definition)",
        "cognizable": "N/A (definition)",
        "keywords": ["cruelty", "definition", "mental cruelty", "harassment", "unlawful demand", "dowry"],
        "transition_note": "The Explanation to IPC 498A is now a separate definition section. Mental cruelty is explicitly included.",
    },
    {
        "id": "bns_87",
        "section": "BNS Section 87",
        "old_ipc": "IPC Section 366",
        "title": "Kidnapping/Abducting Woman to Compel Her Marriage, etc.",
        "description": "Whoever kidnaps or abducts any woman with intent that she may be compelled to marry any person against her will, or that she may be forced or seduced to illicit intercourse, or knowing it likely, shall be punished with imprisonment up to ten years and fine.",
        "punishment": "Up to 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["kidnap", "abduct", "forced marriage", "compel marriage", "seduce", "woman"],
        "transition_note": "Replaces IPC 366. Sits in the offences-against-women chapter, not the kidnapping chapter.",
    },
    {
        "id": "bns_95",
        "section": "BNS Section 95",
        "old_ipc": "New provision (partly IPC 317 concepts)",
        "title": "Hiring, Employing or Engaging a Child to Commit an Offence",
        "description": "Whoever hires, employs or engages any child (person under eighteen) to commit an offence shall be punished with imprisonment of minimum three years extendable to ten years and fine; and if the offence is committed, also punished for that offence as if committed by himself. Engaging a child for sexual exploitation or pornography is covered.",
        "punishment": "3 to 10 years + fine (plus liability for the offence committed)",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["child", "engage", "employ", "hire", "offence", "gang", "exploitation", "minor used for crime"],
        "transition_note": "NEW in BNS \u2014 directly targets using minors to commit crimes.",
    },
    {
        "id": "bns_96",
        "section": "BNS Section 96",
        "old_ipc": "IPC Section 366A",
        "title": "Procuration of Child",
        "description": "Whoever, by any means whatsoever, induces any child to go from any place or to do any act with intent or knowledge that the child will be forced or seduced to illicit intercourse shall be punishable with imprisonment up to ten years and fine.",
        "punishment": "Up to 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["procuration", "child", "minor", "induce", "illicit intercourse", "trafficking"],
        "transition_note": "Replaces IPC 366A; extended from 'minor girl' to any child.",
    },
    {
        "id": "bns_98",
        "section": "BNS Section 98",
        "old_ipc": "IPC Section 372",
        "title": "Selling Child for Purposes of Prostitution, etc.",
        "description": "Whoever sells, lets to hire, or otherwise disposes of any child with intent that the child shall be employed or used for prostitution or illicit intercourse, or for any unlawful and immoral purpose, shall be punished with imprisonment up to ten years and fine.",
        "punishment": "Up to 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["selling child", "prostitution", "hire", "immoral purpose", "trafficking", "brothel"],
        "transition_note": "Replaces IPC 372. Buying a child for the same purpose is BNS 99.",
    },
    {
        "id": "bns_108",
        "section": "BNS Section 108",
        "old_ipc": "IPC Section 306",
        "title": "Abetment of Suicide",
        "description": "If any person commits suicide, whoever abets the commission of such suicide shall be punished with imprisonment up to ten years and fine. Abetment requires instigation, conspiracy or intentional aid (BNS 45). Mere harassment without proximate instigation is not abetment per settled Supreme Court law.",
        "punishment": "Up to 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["suicide", "abetment", "instigation", "harassment", "suicide note", "drive to suicide"],
        "transition_note": "Replaces IPC 306. Abetment of suicide of a child or person of unsound mind is BNS 107 (harsher).",
    },
    {
        "id": "bns_110",
        "section": "BNS Section 110",
        "old_ipc": "IPC Section 308",
        "title": "Attempt to Commit Culpable Homicide",
        "description": "Whoever does any act with such intention or knowledge and under such circumstances that, if he by that act caused death, he would be guilty of culpable homicide not amounting to murder: up to three years or fine or both; if hurt is caused to any person, up to seven years and fine.",
        "punishment": "Up to 3 years (no hurt) / up to 7 years + fine (hurt caused)",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["attempt", "culpable homicide", "grave provocation", "sudden fight", "hurt"],
        "transition_note": "Replaces IPC 308. The lesser cousin of attempt to murder (BNS 109).",
    },
    {
        "id": "bns_112",
        "section": "BNS Section 112",
        "old_ipc": "New provision",
        "title": "Petty Organised Crime",
        "description": "Whoever, being a member of a group or gang, commits theft, snatching, cheating, unauthorised selling of tickets, unauthorised betting or gambling, selling of public examination question papers, or any other similar criminal act, commits petty organised crime: imprisonment of minimum one year extendable to seven years, and fine. Targets mobile organised crime groups/gangs causing general feelings of insecurity.",
        "punishment": "1 to 7 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["gang", "organised", "vehicle theft", "pickpocket", "snatching gang", "ATM fraud", "question paper", "betting", "ticket scalping"],
        "transition_note": "NEW in BNS \u2014 the small-scale counterpart of BNS 111 (organised crime).",
    },
    {
        "id": "bns_114",
        "section": "BNS Section 114",
        "old_ipc": "IPC Section 319",
        "title": "Hurt (Definition)",
        "description": "Whoever causes bodily pain, disease or infirmity to any person is said to cause hurt. Punishment for voluntarily causing hurt is BNS 115.",
        "punishment": "Definition section \u2014 punishment under BNS 115",
        "bailable": "N/A (definition)",
        "cognizable": "N/A (definition)",
        "keywords": ["hurt", "definition", "bodily pain", "disease", "infirmity"],
        "transition_note": "Replaces IPC 319.",
    },
    {
        "id": "bns_116",
        "section": "BNS Section 116",
        "old_ipc": "IPC Section 320",
        "title": "Grievous Hurt (Definition)",
        "description": "Grievous hurt: emasculation; permanent privation of the sight of either eye or hearing of either ear; privation of any member or joint; destruction or permanent impairing of powers of any member or joint; permanent disfiguration of the head or face; fracture or dislocation of a bone or tooth; any hurt which endangers life or which causes the sufferer to be, for fifteen days, in severe bodily pain or unable to follow ordinary pursuits.",
        "punishment": "Definition section \u2014 punishment under BNS 117",
        "bailable": "N/A (definition)",
        "cognizable": "N/A (definition)",
        "keywords": ["grievous hurt", "definition", "fracture", "disfiguration", "loss of sight", "fifteen days"],
        "transition_note": "Replaces IPC 320. The fifteen-day (was twenty-day) disability window is retained at fifteen days for hospital cases.",
    },
    {
        "id": "bns_118",
        "section": "BNS Section 118",
        "old_ipc": "IPC Section 324/326",
        "title": "Hurt or Grievous Hurt by Dangerous Weapons or Means",
        "description": "118(1): Voluntarily causing hurt by any instrument for shooting, stabbing or cutting, or by fire, poison, corrosive/explosive substance, or animal: up to three years, or fine up to twenty thousand rupees, or both. 118(2): Voluntarily causing grievous hurt by such weapons/means: imprisonment for life, or one to ten years and fine.",
        "punishment": "Hurt: up to 3 years or fine up to Rs 20,000 or both; grievous: life, or 1-10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["knife", "weapon", "stab", "acid", "burn", "dangerous weapon", "grievous", "attack"],
        "transition_note": "Replaces IPC 324 (hurt) and IPC 326 (grievous hurt) as subsections (1) and (2).",
    },
    {
        "id": "bns_121",
        "section": "BNS Section 121",
        "old_ipc": "IPC Section 332/333",
        "title": "Hurt or Grievous Hurt to Deter Public Servant from Duty",
        "description": "121(1): Voluntarily causing hurt to a public servant in the discharge of duty, or to prevent/deter discharge of duty: up to five years, or fine, or both. 121(2): Voluntarily causing grievous hurt to a public servant in such circumstances: minimum one year, extendable to ten years, and fine.",
        "punishment": "Hurt: up to 5 years or fine or both; grievous hurt: 1 to 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["public servant", "police", "assault on police", "government officer", "duty", "obstruction"],
        "transition_note": "Replaces IPC 332/333. Punishment for simple hurt raised from 3 to 5 years.",
    },
    {
        "id": "bns_123",
        "section": "BNS Section 123",
        "old_ipc": "IPC Section 328",
        "title": "Causing Hurt by Means of Poison, etc., with Intent to Commit an Offence",
        "description": "Whoever administers or causes to be taken any poison or any stupefying, intoxicating or unwholesome drug with intent to cause hurt, or to facilitate an offence: up to ten years and fine. Covers spiking drinks, sedating victims for robbery, and poisoning.",
        "punishment": "Up to 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["poison", "drug", "spiked drink", "sedative", "intoxicate", "stupefy", "robbery drug"],
        "transition_note": "Replaces IPC 328.",
    },
    {
        "id": "bns_124",
        "section": "BNS Section 124",
        "old_ipc": "IPC Section 326A/326B",
        "title": "Voluntarily Causing Grievous Hurt by Use of Acid, etc. (Acid Attack)",
        "description": "124(1): Whoever causes permanent or partial damage or deformity, burns, maiming, disfigurement, disability, or grievous hurt by throwing or administering acid with the intention or knowledge: rigorous imprisonment of minimum ten years extendable to life, and fine which shall be just and reasonable to meet the medical expenses, payable to the victim. 124(2): Throwing or attempting to throw acid with intent: five to seven years and fine.",
        "punishment": "Acid attack: min 10 years to life + fine paid to victim; attempt: 5-7 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["acid attack", "acid", "corrosive", "disfigurement", "burns", "throw acid", "attempt"],
        "transition_note": "Replaces IPC 326A (attack) and 326B (attempt). Fine goes to the victim's treatment.",
    },
    {
        "id": "bns_126",
        "section": "BNS Section 126",
        "old_ipc": "IPC Section 339/341",
        "title": "Wrongful Restraint",
        "description": "Whoever voluntarily obstructs any person so as to prevent that person from proceeding in any direction in which that person has a right to proceed, is said wrongfully to restrain that person. Punishment (126(2)): simple imprisonment up to one month, or fine up to five thousand rupees, or both. Blocking a person's path or vehicle attracts this section; confining them within limits is the graver BNS 127.",
        "punishment": "Simple imprisonment up to 1 month, or fine up to Rs 5,000, or both",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["restrain", "obstruct", "block", "stop", "path", "gate", "vehicle blocked", "movement"],
        "transition_note": "Replaces IPC 339/341. Fine raised from Rs 500 to Rs 5,000.",
    },
    {
        "id": "bns_130",
        "section": "BNS Section 130",
        "old_ipc": "IPC Section 351",
        "title": "Assault (Definition)",
        "description": "Whoever makes any gesture or preparation intending or knowing it likely that such gesture or preparation will cause any person present to apprehend that criminal force is about to be used, commits an assault. Mere words do not amount to assault, but words may give gestures the meaning of assault.",
        "punishment": "Definition section \u2014 basic punishment BNS 131 (up to 3 months or fine up to Rs 1,000)",
        "bailable": "Bailable",
        "cognizable": "No",
        "keywords": ["assault", "definition", "gesture", "threat of force", "apprehension"],
        "transition_note": "Replaces IPC 351. Aggravated assaults (public servant, modesty, provocation) are BNS 131-136.",
    },
    {
        "id": "bns_132",
        "section": "BNS Section 132",
        "old_ipc": "IPC Section 353",
        "title": "Assault or Criminal Force to Deter Public Servant from Duty",
        "description": "Whoever assaults or uses criminal force to any person being a public servant in the execution of duty, or with intent to prevent or deter discharge of duty: imprisonment up to two years, or fine, or both.",
        "punishment": "Up to 2 years, or fine, or both",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["assault", "public servant", "police", "obstruction", "duty", "criminal force"],
        "transition_note": "Replaces IPC 353. If hurt is caused, BNS 121 applies instead.",
    },
    {
        "id": "bns_137",
        "section": "BNS Section 137",
        "old_ipc": "IPC Section 359/360/361/363",
        "title": "Kidnapping",
        "description": "Kidnapping is of two kinds: from India (conveying beyond the limits of India without consent), and from lawful guardianship (taking or enticing a child under eighteen or a person of unsound mind out of the keeping of the lawful guardian without consent). Punishment (137(2)): imprisonment up to seven years and fine.",
        "punishment": "Up to 7 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["kidnapping", "minor", "guardianship", "child", "taking away", "enticing", "custody"],
        "transition_note": "Consolidates IPC 359-361 (definitions) and 363 (punishment). Abduction is BNS 138.",
    },
    {
        "id": "bns_139",
        "section": "BNS Section 139",
        "old_ipc": "IPC Section 363A",
        "title": "Kidnapping or Maiming a Child for Purposes of Begging",
        "description": "Whoever kidnaps or obtains custody of a child for employing the child for begging: rigorous imprisonment of minimum ten years extendable to life, and fine. Whoever maims a child for begging: imprisonment for life (natural life remainder), and fine.",
        "punishment": "Kidnap for begging: min 10 years to life + fine; maiming: imprisonment for life + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["begging", "child", "maim", "kidnap", "gang", "exploitation"],
        "transition_note": "Replaces IPC 363A with stiffer minimums.",
    },
    {
        "id": "bns_142",
        "section": "BNS Section 142",
        "old_ipc": "IPC Section 368",
        "title": "Wrongfully Concealing or Keeping in Confinement Kidnapped or Abducted Person",
        "description": "Whoever, knowing that a person has been kidnapped or abducted, wrongfully conceals or confines such person, shall be punished in the same manner as if he had kidnapped or abducted the person with the same intention or knowledge.",
        "punishment": "Same as the underlying kidnapping/abduction offence",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["conceal", "confine", "kidnapped person", "harbour", "accomplice"],
        "transition_note": "Replaces IPC 368. Harbourers face the kidnapper's punishment.",
    },
    {
        "id": "bns_144",
        "section": "BNS Section 144",
        "old_ipc": "IPC Section 370A",
        "title": "Exploitation of a Trafficked Person",
        "description": "Whoever engages a trafficked child for sexual exploitation: five to ten years and fine. Whoever engages a trafficked adult for sexual exploitation: three to seven years and fine. Knowledge or reason to believe the person was trafficked suffices.",
        "punishment": "Child: 5-10 years + fine; adult: 3-7 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["trafficking", "exploitation", "sexual exploitation", "trafficked person", "customer liability"],
        "transition_note": "Replaces IPC 370A. Read with BNS 143 (trafficking of person).",
    },
    {
        "id": "bns_152",
        "section": "BNS Section 152",
        "old_ipc": "IPC Section 124A (sedition \u2014 repealed)",
        "title": "Act Endangering Sovereignty, Unity and Integrity of India",
        "description": "Whoever, purposely or knowingly, by words (spoken or written), signs, visible representation, electronic communication, or use of financial means, excites or attempts to excite secession, armed rebellion or subversive activities, or encourages feelings of separatist activities, or endangers the sovereignty, unity and integrity of India: imprisonment for life, or up to seven years, and fine. Explanation: lawful criticism of government measures to obtain their alteration by lawful means is NOT an offence.",
        "punishment": "Imprisonment for life, or up to 7 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["sedition", "sovereignty", "secession", "armed rebellion", "subversive", "separatist", "anti-national", "electronic communication"],
        "transition_note": "Sedition (IPC 124A) is formally repealed; BNS 152 is the successor with a lawful-criticism safeguard. Cite carefully \u2014 152 is NOT simply 'new sedition'.",
    },
    {
        "id": "bns_189",
        "section": "BNS Section 189",
        "old_ipc": "IPC Section 141/143/144/145",
        "title": "Unlawful Assembly",
        "description": "An assembly of five or more persons is unlawful if the common object is to overawe government by criminal force, resist execution of law, commit mischief or criminal trespass, take property by force, or compel a person to do an illegal act. Member: up to six months, or fine, or both (189(2)). Joining armed with a deadly weapon: up to two years, or fine, or both (189(4)).",
        "punishment": "Member: up to 6 months or fine or both; armed with deadly weapon: up to 2 years or fine or both",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["unlawful assembly", "five or more", "common object", "mob", "protest", "riot"],
        "transition_note": "Consolidates IPC 141-145. Rioting (violence by unlawful assembly) is BNS 191.",
    },
    {
        "id": "bns_190",
        "section": "BNS Section 190",
        "old_ipc": "IPC Section 149",
        "title": "Every Member of Unlawful Assembly Guilty of Offence Committed in Prosecution of Common Object",
        "description": "If an offence is committed by any member of an unlawful assembly in prosecution of the common object, or such as the members knew to be likely, every person who was a member at the time is guilty of that offence. This is the constructive/vicarious liability backbone of mob-violence prosecutions.",
        "punishment": "Same punishment as the offence committed by the assembly",
        "bailable": "Per underlying offence",
        "cognizable": "Per underlying offence",
        "keywords": ["common object", "vicarious liability", "mob", "every member", "constructive liability"],
        "transition_note": "Replaces IPC 149 \u2014 charge it alongside the substantive offence (e.g. BNS 103 + 190).",
    },
    {
        "id": "bns_194",
        "section": "BNS Section 194",
        "old_ipc": "IPC Section 159/160",
        "title": "Affray",
        "description": "When two or more persons, by fighting in a public place, disturb the public peace, they are said to commit an affray: imprisonment up to one month, or fine up to one thousand rupees, or both.",
        "punishment": "Up to 1 month, or fine up to Rs 1,000, or both",
        "bailable": "Bailable",
        "cognizable": "No",
        "keywords": ["affray", "public fight", "street fight", "brawl", "public peace"],
        "transition_note": "Replaces IPC 159/160.",
    },
    {
        "id": "bns_238",
        "section": "BNS Section 238",
        "old_ipc": "IPC Section 201",
        "title": "Causing Disappearance of Evidence of Offence, or Giving False Information to Screen Offender",
        "description": "Whoever, knowing an offence has been committed, causes evidence of the offence to disappear to screen the offender, or gives false information: if the offence is punishable with death \u2014 up to seven years and fine; if punishable with life or 10+ years \u2014 up to three years and fine; otherwise \u2014 up to one-fourth of the longest term for the offence, or fine, or both.",
        "punishment": "Capital offence: up to 7 years + fine; life/10-year offence: up to 3 years + fine; else lesser",
        "bailable": "Depends on underlying offence",
        "cognizable": "Depends on underlying offence",
        "keywords": ["destroy evidence", "disappearance of evidence", "screen offender", "false information", "cover up", "tamper"],
        "transition_note": "Replaces IPC 201. Common add-on charge in murder cover-ups.",
    },
    {
        "id": "bns_281",
        "section": "BNS Section 281",
        "old_ipc": "IPC Section 279",
        "title": "Rash Driving or Riding on a Public Way",
        "description": "Whoever drives any vehicle, or rides, on any public way in a manner so rash or negligent as to endanger human life, or to be likely to cause hurt or injury: imprisonment up to six months, or fine up to one thousand rupees, or both. If death results, BNS 106 applies; Motor Vehicles Act offences apply in parallel.",
        "punishment": "Up to 6 months, or fine up to Rs 1,000, or both",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["rash driving", "negligent driving", "accident", "public way", "endanger", "traffic"],
        "transition_note": "Replaces IPC 279. Death cases go to BNS 106 (with the 106(2) hit-and-run aggravation).",
    },
    {
        "id": "bns_298",
        "section": "BNS Section 298",
        "old_ipc": "IPC Section 295",
        "title": "Injuring or Defiling Place of Worship with Intent to Insult the Religion of Any Class",
        "description": "Whoever destroys, damages or defiles any place of worship or any object held sacred, with the intention of thereby insulting the religion of any class of persons, or with knowledge that it is likely to be so considered: up to two years, or fine, or both.",
        "punishment": "Up to 2 years, or fine, or both",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["place of worship", "temple", "mosque", "church", "defile", "sacred", "religion"],
        "transition_note": "Replaces IPC 295.",
    },
    {
        "id": "bns_299",
        "section": "BNS Section 299",
        "old_ipc": "IPC Section 295A",
        "title": "Deliberate and Malicious Acts Intended to Outrage Religious Feelings",
        "description": "Whoever, with deliberate and malicious intention of outraging the religious feelings of any class, by words, signs, visible representations or electronic means, insults or attempts to insult the religion or religious beliefs of that class: up to three years, or fine, or both.",
        "punishment": "Up to 3 years, or fine, or both",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["religious feelings", "insult religion", "malicious", "blasphemy", "social media post"],
        "transition_note": "Replaces IPC 295A; electronic means now explicit.",
    },
    {
        "id": "bns_305",
        "section": "BNS Section 305",
        "old_ipc": "IPC Section 380",
        "title": "Theft in a Dwelling House, Means of Transportation or Place of Worship",
        "description": "Whoever commits theft in any building, tent or vessel used as a human dwelling or for custody of property, or of any means of transportation used for transport of goods or passengers, or of any article from a place of worship, or of government property: imprisonment up to seven years and fine.",
        "punishment": "Up to 7 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["house theft", "dwelling", "vehicle theft", "temple theft", "burglary", "government property"],
        "transition_note": "Replaces IPC 380, widened to vehicles, places of worship and government property.",
    },
    {
        "id": "bns_306",
        "section": "BNS Section 306",
        "old_ipc": "IPC Section 381",
        "title": "Theft by Clerk or Servant of Property in Possession of Master",
        "description": "Whoever, being a clerk or servant, commits theft of any property in the possession of his master or employer: imprisonment up to seven years and fine.",
        "punishment": "Up to 7 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["employee theft", "servant", "clerk", "domestic help", "employer", "office theft"],
        "transition_note": "Replaces IPC 381. Distinct from criminal breach of trust (BNS 316) where property was entrusted.",
    },
    {
        "id": "bns_308",
        "section": "BNS Section 308",
        "old_ipc": "IPC Section 383/384",
        "title": "Extortion",
        "description": "Whoever intentionally puts any person in fear of injury to that person or any other, and thereby dishonestly induces the person so put in fear to deliver property, valuable security or anything signed/sealed convertible into a valuable security, commits extortion. Punishment (308(2)): up to seven years, or fine, or both. Aggravated forms (fear of death/grievous hurt): up to ten years.",
        "punishment": "Up to 7 years, or fine, or both; by threat of death/grievous hurt: higher",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["extortion", "blackmail", "threat", "protection money", "ransom demand", "fear of injury", "sextortion"],
        "transition_note": "Replaces IPC 383-389 as one section with subsections. Online sextortion is charged here.",
    },
    {
        "id": "bns_317",
        "section": "BNS Section 317",
        "old_ipc": "IPC Section 410/411",
        "title": "Stolen Property",
        "description": "Property whose possession has been transferred by theft, extortion, robbery, cheating, or criminal misappropriation/breach of trust is stolen property. Dishonestly receiving or retaining stolen property knowing or having reason to believe it stolen (317(2)): up to three years, or fine, or both. Habitual dealing (317(5)): up to life or 10 years.",
        "punishment": "Receiving: up to 3 years or fine or both; habitual receiver: up to life or 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["stolen property", "receiver", "fence", "second-hand", "knowingly", "recovered goods"],
        "transition_note": "Replaces IPC 410-414. The charge against buyers of stolen phones/vehicles.",
    },
    {
        "id": "bns_319",
        "section": "BNS Section 319",
        "old_ipc": "IPC Section 416/419",
        "title": "Cheating by Personation",
        "description": "A person cheats by personation if he cheats by pretending to be some other person, or by knowingly substituting one person for another, or representing that he or any other person is a person other than he really is. Punishment (319(2)): up to five years, or fine, or both. Covers fake officials, impersonation in exams, and online identity fraud (read with IT Act 66D for computer-resource impersonation).",
        "punishment": "Up to 5 years, or fine, or both",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["impersonation", "fake identity", "fake officer", "army officer scam", "exam", "OLX fraud", "personation", "identity fraud"],
        "transition_note": "Replaces IPC 416/419; punishment raised from 3 to 5 years. Pair with IT Act 66D online.",
    },
    {
        "id": "bns_324",
        "section": "BNS Section 324",
        "old_ipc": "IPC Section 425/426/427",
        "title": "Mischief",
        "description": "Whoever, with intent to cause wrongful loss or damage, causes the destruction of any property or any change that destroys or diminishes its value or utility, commits mischief. Punishment: up to six months, or fine, or both (324(2)); damage of Rs 20,000 to 1 lakh: up to two years (324(4)); damage of Rs 1 lakh or more: up to five years (324(5)).",
        "punishment": "Up to 6 months basic; up to 2 years (loss >= Rs 20,000); up to 5 years (loss >= Rs 1 lakh)",
        "bailable": "Bailable (basic)",
        "cognizable": "No (basic); higher forms cognizable",
        "keywords": ["mischief", "property damage", "vandalism", "damage", "destruction", "car scratched"],
        "transition_note": "Replaces IPC 425-427 with value-based slabs.",
    },
    {
        "id": "bns_326",
        "section": "BNS Section 326",
        "old_ipc": "IPC Section 435/436",
        "title": "Mischief by Injury, Inundation, Fire or Explosive Substance, etc.",
        "description": "Mischief by fire or explosive substance intending or knowing it likely to cause damage: up to seven years and fine (326(f)); where the fire/explosive destroys a building used as a place of worship, human dwelling or property custody: imprisonment for life or up to ten years and fine (326(g)).",
        "punishment": "Fire/explosive: up to 7 years + fine; dwelling/worship building: life or up to 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["arson", "fire", "explosive", "burn house", "inundation", "flood", "property destruction"],
        "transition_note": "Replaces IPC 435/436.",
    },
    {
        "id": "bns_329",
        "section": "BNS Section 329",
        "old_ipc": "IPC Section 441/442/447/448",
        "title": "Criminal Trespass and House-Trespass",
        "description": "Criminal trespass: entering property in possession of another with intent to commit an offence or to intimidate, insult or annoy, or unlawfully remaining there with such intent. House-trespass: criminal trespass into any building, tent or vessel used as a human dwelling, place of worship or place for custody of property. Punishment: criminal trespass \u2014 up to three months or fine up to Rs 5,000 or both (329(3)); house-trespass \u2014 up to one year or fine up to Rs 5,000 or both (329(4)).",
        "punishment": "Trespass: up to 3 months or Rs 5,000 fine; house-trespass: up to 1 year or Rs 5,000 fine",
        "bailable": "Bailable",
        "cognizable": "Yes",
        "keywords": ["trespass", "house trespass", "entered property", "unlawful entry", "annoy", "intimidate"],
        "transition_note": "Consolidates IPC 441-448. House-breaking and aggravated forms are BNS 330-334.",
    },
    {
        "id": "bns_331",
        "section": "BNS Section 331",
        "old_ipc": "IPC Section 453-456",
        "title": "Punishment for House-Trespass or House-Breaking",
        "description": "House-trespass/house-breaking: up to two years and fine; committed after sunset and before sunrise (night): up to three years. To commit an imprisonable offence: up to three years (ten if theft intended); at night with such intent: up to five years (fourteen if theft). With preparation for causing hurt/assault/restraint: up to ten years; at night: up to fourteen years.",
        "punishment": "2-3 years basic (day/night); up to 10-14 years with theft intent or preparation for hurt",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["house breaking", "burglary", "break in", "night", "lurking", "housebreaking theft"],
        "transition_note": "Consolidates IPC 453-456 with day/night and intent-based slabs.",
    },
    {
        "id": "bns_335",
        "section": "BNS Section 335",
        "old_ipc": "IPC Section 464",
        "title": "Making a False Document",
        "description": "A person makes a false document or false electronic record who dishonestly or fraudulently makes, signs, seals, executes or transmits a document, alters a document without lawful authority, or causes a person to execute a document knowing he does not understand its contents. This is the definitional foundation of forgery (BNS 336).",
        "punishment": "Definition section \u2014 punishments under BNS 336-340",
        "bailable": "N/A (definition)",
        "cognizable": "N/A (definition)",
        "keywords": ["false document", "electronic record", "definition", "signature", "alteration"],
        "transition_note": "Replaces IPC 464; electronic records included.",
    },
    {
        "id": "bns_338",
        "section": "BNS Section 338",
        "old_ipc": "IPC Section 467",
        "title": "Forgery of Valuable Security, Will, etc.",
        "description": "Whoever forges a document purporting to be a valuable security, a will, an authority to adopt, or a power of attorney/receipt for money or property: imprisonment for life, or up to ten years, and fine.",
        "punishment": "Imprisonment for life, or up to 10 years + fine",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["forged will", "valuable security", "power of attorney", "property documents", "cheque forgery"],
        "transition_note": "Replaces IPC 467. The land-fraud and forged-will workhorse.",
    },
    {
        "id": "bns_340",
        "section": "BNS Section 340",
        "old_ipc": "IPC Section 470/471",
        "title": "Forged Document or Electronic Record and Using It as Genuine",
        "description": "A forged document or electronic record is one made wholly or in part by forgery. Whoever fraudulently or dishonestly uses as genuine any document which he knows or has reason to believe to be forged (340(2)): punished in the same manner as if he had forged it.",
        "punishment": "Using forged document: same punishment as forgery of that document",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["using forged document", "fake certificate", "fake degree", "forged mark sheet", "genuine use"],
        "transition_note": "Replaces IPC 470/471. Submitting a forged document = forging it, punishment-wise.",
    },
    {
        "id": "bns_344",
        "section": "BNS Section 344",
        "old_ipc": "IPC Section 477A",
        "title": "Falsification of Accounts",
        "description": "Whoever, being a clerk, officer or servant, wilfully and with intent to defraud destroys, alters, mutilates or falsifies any book, electronic record, paper, writing, valuable security or account belonging to or in possession of his employer, or makes any false entry: up to seven years, or fine, or both.",
        "punishment": "Up to 7 years, or fine, or both",
        "bailable": "Bailable",
        "cognizable": "No",
        "keywords": ["falsification", "accounts", "false entry", "books", "audit fraud", "embezzlement records"],
        "transition_note": "Replaces IPC 477A. Pairs with BNS 316 (criminal breach of trust) in employee-fraud cases.",
    },
    {
        "id": "bns_352",
        "section": "BNS Section 352",
        "old_ipc": "IPC Section 504",
        "title": "Intentional Insult with Intent to Provoke Breach of the Peace",
        "description": "Whoever intentionally insults in any manner, and thereby gives provocation to any person, intending or knowing it likely that such provocation will cause him to break the public peace or commit any other offence: up to two years, or fine, or both.",
        "punishment": "Up to 2 years, or fine, or both",
        "bailable": "Bailable",
        "cognizable": "No",
        "keywords": ["insult", "provoke", "abuse", "verbal abuse", "breach of peace", "gaali"],
        "transition_note": "Replaces IPC 504.",
    },
    {
        "id": "bns_353",
        "section": "BNS Section 353",
        "old_ipc": "IPC Section 505",
        "title": "Statements Conducing to Public Mischief",
        "description": "Whoever makes, publishes or circulates any statement, false information, rumour or report (including through electronic means) with intent to cause mutiny, or fear or alarm to the public whereby a person may be induced to commit an offence against the State or public tranquillity, or to incite any class or community against another: up to three years, or fine, or both. In a place of worship etc.: up to five years.",
        "punishment": "Up to 3 years, or fine, or both (up to 5 years in a place of worship etc.)",
        "bailable": "Non-bailable",
        "cognizable": "Yes",
        "keywords": ["fake news", "rumour", "WhatsApp forward", "public mischief", "false information", "communal", "incite", "panic"],
        "transition_note": "Replaces IPC 505; explicitly covers electronic circulation \u2014 the fake-news/rumour section.",
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
