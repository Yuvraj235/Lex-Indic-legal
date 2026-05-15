"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LEX-INDIC — BNSS + BSA Knowledge Base (Day 11)                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT: The two procedural / evidentiary codes that came into force alongside
the BNS on 1 July 2024.

  - BNSS (Bharatiya Nagarik Suraksha Sanhita, 2023)
     Replaces the Code of Criminal Procedure 1973 (CrPC).
     Governs FIR registration, arrest, bail, investigation, trial, appeal.
  - BSA  (Bharatiya Sakshya Adhiniyam, 2023)
     Replaces the Indian Evidence Act 1872.
     Governs admissibility, burden of proof, electronic evidence, etc.

Most lawyers using Lex-Indic for criminal triage need BNSS sections too —
"under which section do I file for bail?", "what's the new arrest procedure
notice?", "is this 65B certificate compliant under BSA?".  Without these,
the engine's output is incomplete.

We curate 18 BNSS + 8 BSA sections — the highest-citation provisions in
Indian criminal practice.  Schema mirrors data/bns_knowledge_base.py so
the same RAG pipeline indexes them.
"""

from __future__ import annotations


BNSS_SECTIONS = [
    # ─── FIR + Investigation ─────────────────────────────────────────────
    {
        "id": "bnss_173",
        "section": "BNSS Section 173",
        "old_ipc": "CrPC Section 154",
        "title": "Information in Cognizable Cases (FIR Registration)",
        "description": (
            "Every information relating to the commission of a cognizable "
            "offence, if given orally to an officer in charge of a police "
            "station, shall be reduced to writing by him or under his "
            "direction, and be read over to the informant.  The substance "
            "shall be entered in a book to be kept by such officer in such "
            "form as the State Government may prescribe.  Police MUST "
            "register an FIR — Lalita Kumari (2014) directive remains "
            "fully applicable under BNSS."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["FIR", "first information report", "register FIR",
                     "police refuse FIR", "SHO", "cognizable offence",
                     "Lalita Kumari", "information"],
        "transition_note": "Replaces CrPC 154. The Lalita Kumari mandate continues. Refusal to register a cognizable-offence FIR is actionable under BNSS 175(3) before the Magistrate.",
    },
    {
        "id": "bnss_175",
        "section": "BNSS Section 175",
        "old_ipc": "CrPC Section 156",
        "title": "Police Officer's Power to Investigate",
        "description": (
            "Any officer in charge of a police station may, without the "
            "order of a Magistrate, investigate any cognizable case which "
            "a court having jurisdiction over the local area within the "
            "limits of such station would have power to inquire into or "
            "try.  BNSS 175(3): If the SHO refuses to register an FIR "
            "for a cognizable offence, the aggrieved person may approach "
            "the Magistrate, who can order investigation."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["investigation", "police powers", "Magistrate order",
                     "SHO refuses FIR", "175(3)"],
        "transition_note": "Replaces CrPC 156. The 156(3) Magistrate-order path is preserved under BNSS 175(3).",
    },

    # ─── Arrest procedure ────────────────────────────────────────────────
    {
        "id": "bnss_35",
        "section": "BNSS Section 35",
        "old_ipc": "CrPC Section 41A",
        "title": "Notice of Appearance (Arrest Procedure)",
        "description": (
            "The police officer shall, in all cases where the arrest of a "
            "person is not required under sub-section (1) of section 35, "
            "issue a notice directing the person against whom a reasonable "
            "complaint has been made, or credible information has been "
            "received, or a reasonable suspicion exists that he has "
            "committed a cognizable offence, to appear before him.  Where "
            "such notice is issued and complied with, the person shall not "
            "be arrested unless the police officer, for reasons to be "
            "recorded, is of opinion that he ought to be arrested."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["arrest procedure", "41A notice", "notice of appearance",
                     "Arnesh Kumar", "BNS 85 arrest", "no arrest before notice"],
        "transition_note": "Replaces CrPC 41A.  Arnesh Kumar v Bihar (2014) guidelines apply with full force — police must issue notice for offences punishable up to 7 years.",
    },
    {
        "id": "bnss_43",
        "section": "BNSS Section 43",
        "old_ipc": "CrPC Section 46",
        "title": "Arrest How Made",
        "description": (
            "In making an arrest the police officer or other person making "
            "the same shall actually touch or confine the body of the "
            "person to be arrested, unless there be a submission to the "
            "custody by word or action.  An arrested woman cannot be "
            "arrested by a male police officer, and after sunset and "
            "before sunrise, except in exceptional circumstances with "
            "written authorisation from a JMFC."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["arrest", "arrest of woman", "night arrest", "female arrest",
                     "physical custody"],
        "transition_note": "Replaces CrPC 46. The female-arrest-by-female-officer requirement is statutory.",
    },

    # ─── Bail provisions ─────────────────────────────────────────────────
    {
        "id": "bnss_480",
        "section": "BNSS Section 480",
        "old_ipc": "CrPC Section 437",
        "title": "When Bail May Be Taken in Case of Non-Bailable Offence",
        "description": (
            "When any person accused of, or suspected of, the commission "
            "of any non-bailable offence is arrested or detained without "
            "warrant by an officer in charge of a police station or "
            "appears or is brought before a Court other than the High "
            "Court or Court of Session, he may be released on bail.  The "
            "Court must record reasons in writing if bail is refused."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["bail", "non-bailable", "regular bail", "bail application",
                     "Magistrate bail"],
        "transition_note": "Replaces CrPC 437. The 'reasons in writing for refusal' requirement is enforced more strictly under BNSS.",
    },
    {
        "id": "bnss_482",
        "section": "BNSS Section 482",
        "old_ipc": "CrPC Section 438",
        "title": "Anticipatory Bail (Direction for Grant of Bail to Person Apprehending Arrest)",
        "description": (
            "When any person has reason to believe that he may be arrested "
            "on accusation of having committed a non-bailable offence, he "
            "may apply to the High Court or the Court of Session for a "
            "direction under this section.  The court may, after taking "
            "into consideration the nature and gravity of the accusation, "
            "the antecedents of the applicant, the possibility of fleeing, "
            "etc., grant anticipatory bail."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["anticipatory bail", "AB", "pre-arrest bail", "438",
                     "section session court", "high court bail"],
        "transition_note": "Replaces CrPC 438. UP/MP-specific deletions under CrPC are restored; 438 is now available in all states.",
    },
    {
        "id": "bnss_483",
        "section": "BNSS Section 483",
        "old_ipc": "CrPC Section 439",
        "title": "Special Powers of High Court or Court of Session Regarding Bail",
        "description": (
            "A High Court or Court of Session may direct that any person "
            "accused of an offence and in custody be released on bail; "
            "and may, in any case, impose any condition which it considers "
            "necessary.  Cancellation of bail also available under this "
            "section."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["bail", "high court bail", "session court bail",
                     "cancellation of bail", "439"],
        "transition_note": "Replaces CrPC 439. Higher court's residual bail jurisdiction preserved.",
    },

    # ─── Search & seizure ────────────────────────────────────────────────
    {
        "id": "bnss_103",
        "section": "BNSS Section 103",
        "old_ipc": "CrPC Section 100",
        "title": "Persons in Charge of Closed Place to Allow Search",
        "description": (
            "Whenever any place liable to search or inspection under this "
            "Sanhita is closed, any person residing in, or being in "
            "charge of, such place, shall, on demand of the officer or "
            "other person executing the warrant, and on production of "
            "the warrant, allow him free ingress thereto, and afford all "
            "reasonable facilities for a search therein.  Search must be "
            "conducted in the presence of two independent witnesses."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["search", "seizure", "search warrant", "independent witnesses",
                     "panchnama"],
        "transition_note": "Replaces CrPC 100. The 'two independent witnesses' / panchnama requirement is statutory.",
    },

    # ─── Trial & sentencing ──────────────────────────────────────────────
    {
        "id": "bnss_223",
        "section": "BNSS Section 223",
        "old_ipc": "CrPC Section 200",
        "title": "Examination of Complainant (Private Complaint)",
        "description": (
            "A Magistrate taking cognizance of an offence on complaint "
            "shall examine upon oath the complainant and the witnesses "
            "present, if any, and the substance of such examination "
            "shall be reduced to writing and shall be signed by the "
            "complainant and the witnesses, and also by the Magistrate."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["private complaint", "200", "magistrate cognizance",
                     "examination of complainant"],
        "transition_note": "Replaces CrPC 200. Standard route when police refuse to register an FIR.",
    },
    {
        "id": "bnss_528",
        "section": "BNSS Section 528",
        "old_ipc": "CrPC Section 482",
        "title": "Saving of Inherent Powers of High Court",
        "description": (
            "Nothing in this Sanhita shall be deemed to limit or affect "
            "the inherent powers of the High Court to make such orders "
            "as may be necessary to give effect to any order under this "
            "Sanhita, or to prevent abuse of the process of any Court "
            "or otherwise to secure the ends of justice.  This is the "
            "route for quashing FIRs based on settlement or where "
            "continuing the proceedings would be a manifest injustice."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["quash FIR", "482", "inherent powers", "quashing",
                     "high court inherent powers", "settlement"],
        "transition_note": "Replaces CrPC 482. The Gian Singh / Narinder Singh quashing jurisprudence remains intact under BNSS 528.",
    },

    # ─── Statements & evidence (procedural) ──────────────────────────────
    {
        "id": "bnss_180",
        "section": "BNSS Section 180",
        "old_ipc": "CrPC Section 161",
        "title": "Examination of Witnesses by Police",
        "description": (
            "Any police officer making an investigation under this "
            "Sanhita may examine orally any person supposed to be "
            "acquainted with the facts and circumstances of the case.  "
            "Such person shall be bound to answer truly all questions "
            "relating to the case put to him by such officer, other "
            "than questions the answers to which would have a tendency "
            "to expose him to a criminal charge or to a penalty or "
            "forfeiture."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["161 statement", "police statement", "witness statement",
                     "investigation"],
        "transition_note": "Replaces CrPC 161. 161 statements remain inadmissible as substantive evidence; only usable for contradiction under BSA 158.",
    },
    {
        "id": "bnss_183",
        "section": "BNSS Section 183",
        "old_ipc": "CrPC Section 164",
        "title": "Recording of Confessions and Statements by Magistrate",
        "description": (
            "Any Magistrate of the first class may, whether or not he has "
            "jurisdiction in the case, record any confession or statement "
            "made to him in the course of an investigation under this "
            "Sanhita or under any other law for the time being in force, "
            "or at any time afterwards before the commencement of the "
            "inquiry or trial.  The Magistrate shall explain to the "
            "person making the confession that he is not bound to make a "
            "confession and that, if he does so, it may be used against "
            "him."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["164 statement", "judicial confession", "magistrate confession",
                     "voluntary statement"],
        "transition_note": "Replaces CrPC 164.  Recorded with audio-video where possible, per Shafhi Mohammad (2018) directive.",
    },

    # ─── Sentencing / penalties ──────────────────────────────────────────
    {
        "id": "bnss_356",
        "section": "BNSS Section 356",
        "old_ipc": "CrPC Section 317",
        "title": "Trial in Absentia of Proclaimed Offender",
        "description": (
            "Where it is proved that an accused person has absconded and "
            "that there is no immediate prospect of arresting him, the "
            "Court competent to try such person for the offence may, in "
            "his absence, examine the witnesses (if any) produced on "
            "behalf of the prosecution, and record their depositions and "
            "any such deposition may, on the arrest of such person, be "
            "given in evidence against him on the inquiry into, or trial "
            "for, the offence with which he is charged, if the deponent "
            "is dead or incapable of giving evidence or cannot be found."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["trial in absentia", "proclaimed offender", "absconder",
                     "ex-parte trial"],
        "transition_note": "Replaces CrPC 317. BNSS now explicitly permits in-absentia trial of declared proclaimed offenders for serious offences.",
    },

    # ─── Compounding ─────────────────────────────────────────────────────
    {
        "id": "bnss_359",
        "section": "BNSS Section 359",
        "old_ipc": "CrPC Section 320",
        "title": "Compounding of Offences",
        "description": (
            "Lists the offences which may be compounded by the persons "
            "specified, and those which may be compounded only with the "
            "permission of the Court.  Includes a schedule of compoundable "
            "offences (e.g. hurt under BNS 115(2), defamation under BNS "
            "356, etc.).  Non-compoundable offences (rape, murder) cannot "
            "be compounded even with the consent of the victim."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["compoundable", "compounding", "settlement", "320",
                     "withdraw complaint"],
        "transition_note": "Replaces CrPC 320. Schedule of compoundable offences updated to reflect BNS section numbers.",
    },

    # ─── Special — electronic mode of trial ──────────────────────────────
    {
        "id": "bnss_530",
        "section": "BNSS Section 530",
        "old_ipc": "(NEW)",
        "title": "Trial Inquiries and Proceedings in Electronic Mode",
        "description": (
            "All trials, inquiries and proceedings under this Sanhita, "
            "including the issuance, service and execution of summons "
            "and warrant, examination of complainant and witnesses, "
            "recording of evidence in inquiries and trials, and all "
            "appellate proceedings or any other proceedings, may be "
            "held in electronic mode, by use of electronic communication "
            "or use of audio-video electronic means."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["e-court", "electronic trial", "video conferencing",
                     "remote hearing", "audio-video"],
        "transition_note": "NEW in BNSS — full statutory backing for e-court proceedings. Implements the 'digital first' direction from Supreme Court e-Courts Phase III.",
    },

    # ─── Victim rights ────────────────────────────────────────────────────
    {
        "id": "bnss_396",
        "section": "BNSS Section 396",
        "old_ipc": "CrPC Section 357A",
        "title": "Victim Compensation Scheme",
        "description": (
            "Every State Government in coordination with the Central "
            "Government shall prepare a scheme for providing funds for "
            "the purpose of compensation to the victim or his dependants "
            "who have suffered loss or injury as a result of the crime "
            "and who require rehabilitation.  The District Legal Services "
            "Authority or State Legal Services Authority decides the "
            "quantum of compensation."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["victim compensation", "357A", "DLSA", "SLSA",
                     "victim rights", "rehabilitation"],
        "transition_note": "Replaces CrPC 357A.  Victim compensation scheme retained; quantum decided by DLSA/SLSA.",
    },

    # ─── Police interrogation rights ─────────────────────────────────────
    {
        "id": "bnss_36",
        "section": "BNSS Section 36",
        "old_ipc": "CrPC Section 41B",
        "title": "Procedure of Arrest and Duties of Officer Making Arrest",
        "description": (
            "Every police officer while making an arrest shall (a) bear "
            "an accurate, visible and clear identification of his name; "
            "(b) prepare a memorandum of arrest which shall be attested "
            "by at least one witness, who is a member of the family of "
            "the arrestee or a respectable member of the locality where "
            "the arrest is made; and (c) inform the arrestee, unless the "
            "memorandum is attested by a family member, that he has a "
            "right to have a relative or a friend named by him to be "
            "informed of his arrest."
        ),
        "punishment": "N/A (procedural)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["arrest memo", "41B", "arrest identification",
                     "DK Basu", "arrest procedure"],
        "transition_note": "Replaces CrPC 41B. DK Basu v West Bengal (1997) guidelines codified.",
    },
]


BSA_SECTIONS = [
    {
        "id": "bsa_61",
        "section": "BSA Section 61",
        "old_ipc": "Indian Evidence Act Section 65A",
        "title": "Admissibility of Electronic Records",
        "description": (
            "The contents of electronic records may be proved in "
            "accordance with the provisions of section 63.  Electronic "
            "records produced in a court must satisfy the conditions in "
            "section 63 (formerly 65B) for admissibility — namely, the "
            "device must have been in proper working order, the "
            "information must have been regularly fed into the device, "
            "and the device must have been under the lawful control of "
            "the person producing the record."
        ),
        "punishment": "N/A (evidentiary)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["electronic evidence", "65A", "admissibility",
                     "digital evidence", "screenshots"],
        "transition_note": "Replaces IEA 65A. The 'digital first' approach now stronger — physical primary-evidence requirement relaxed.",
    },
    {
        "id": "bsa_63",
        "section": "BSA Section 63",
        "old_ipc": "Indian Evidence Act Section 65B",
        "title": "Admissibility of Electronic Records (65B Certificate)",
        "description": (
            "Where any information contained in an electronic record is "
            "to be used as evidence, a certificate identifying the "
            "electronic record, containing the particulars in sub-section "
            "(4), and signed by a person occupying a responsible official "
            "position in relation to the operation of the relevant device "
            "or the management of the relevant activities, shall be "
            "evidence of any matter stated in the certificate.  The "
            "certificate is MANDATORY; without it, the electronic "
            "evidence is inadmissible (Anvar P.V. v P.K. Basheer, 2014)."
        ),
        "punishment": "N/A (evidentiary)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["65B certificate", "section 65B", "electronic certificate",
                     "Anvar", "Arjun Panditrao", "WhatsApp evidence"],
        "transition_note": "Replaces IEA 65B. The Arjun Panditrao Khotkar (2020) ruling stands — 65B certificate is mandatory at trial; can be filed after preliminary stage with court's permission.",
    },
    {
        "id": "bsa_53",
        "section": "BSA Section 53",
        "old_ipc": "Indian Evidence Act Section 25",
        "title": "Confession to Police Officer Not To Be Proved",
        "description": (
            "No confession made to a police officer shall be proved as "
            "against a person accused of any offence.  This is the "
            "cornerstone protection against coerced confessions during "
            "investigation.  Statements admissible only under BNSS 183 "
            "(Magistrate-recorded) or as a 'discovery' under BSA 27."
        ),
        "punishment": "N/A (evidentiary)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["police confession", "section 25", "coerced confession",
                     "self-incrimination", "Article 20(3)"],
        "transition_note": "Replaces IEA 25. The bar on police confessions is absolute and a Constitutional Article 20(3) safeguard.",
    },
    {
        "id": "bsa_117",
        "section": "BSA Section 117",
        "old_ipc": "Indian Evidence Act Section 113B",
        "title": "Presumption as to Dowry Death",
        "description": (
            "When the question is whether a person has committed the "
            "dowry death of a woman and it is shown that soon before "
            "her death such woman had been subjected by such person to "
            "cruelty or harassment for, or in connection with, any "
            "demand for dowry, the court shall presume that such "
            "person had caused the dowry death.  Rebuttable but "
            "burden squarely on the accused."
        ),
        "punishment": "N/A (evidentiary)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["dowry death presumption", "113B", "shifted burden",
                     "BNS 84"],
        "transition_note": "Replaces IEA 113B. Read with BNS 84 (Dowry Death). The reverse-burden remains intact.",
    },
    {
        "id": "bsa_118",
        "section": "BSA Section 118",
        "old_ipc": "Indian Evidence Act Section 114",
        "title": "Court May Presume Existence of Certain Facts",
        "description": (
            "The Court may presume the existence of any fact which it "
            "thinks likely to have happened, regard being had to the "
            "common course of natural events, human conduct and public "
            "and private business, in their relation to the facts of "
            "the particular case.  Used heavily in possession-of-stolen-"
            "property cases (BNS 317), recovery from accused, etc."
        ),
        "punishment": "N/A (evidentiary)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["presumption", "114", "may presume", "recent possession",
                     "natural inference"],
        "transition_note": "Replaces IEA 114. Most-cited evidentiary presumption section in Indian criminal practice.",
    },
    {
        "id": "bsa_27",
        "section": "BSA Section 23(2)",
        "old_ipc": "Indian Evidence Act Section 27",
        "title": "How Much of Information Received from Accused May Be Proved (Discovery)",
        "description": (
            "When any fact is deposed to as discovered in consequence "
            "of information received from a person accused of any "
            "offence, in the custody of a police officer, so much of "
            "such information, whether it amounts to a confession or "
            "not, as relates distinctly to the fact thereby discovered, "
            "may be proved.  This is the exception to BSA 53 that "
            "lets the prosecution use the 'I will show you where I "
            "hid the body / weapon' type statements."
        ),
        "punishment": "N/A (evidentiary)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["discovery", "section 27", "Pulukuri Kottaya",
                     "recovery statement", "leads to discovery"],
        "transition_note": "Replaces IEA 27 (now numbered 23(2) in BSA). Pulukuri Kottaya (1947) jurisprudence intact.",
    },
    {
        "id": "bsa_24",
        "section": "BSA Section 24",
        "old_ipc": "Indian Evidence Act Section 26",
        "title": "Confession by Accused While in Police Custody Not to be Proved",
        "description": (
            "No confession made by any person whilst he is in the "
            "custody of a police officer, unless it be made in the "
            "immediate presence of a Magistrate, shall be proved as "
            "against such person.  This complements BSA 53 — together "
            "they create the architecture of protection against "
            "custodial confessions."
        ),
        "punishment": "N/A (evidentiary)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["custodial confession", "26", "police custody",
                     "Magistrate presence", "Article 20(3)"],
        "transition_note": "Replaces IEA 26. Read with BSA 53 and BNSS 183.",
    },
    {
        "id": "bsa_46",
        "section": "BSA Section 46",
        "old_ipc": "Indian Evidence Act Section 53A",
        "title": "Evidence of Character or Previous Sexual Experience Not Relevant in Certain Cases",
        "description": (
            "In a prosecution for an offence under BNS sections 64 to "
            "73 (sexual offences) where the question of consent is in "
            "issue, evidence of the character of the victim or of such "
            "victim's previous sexual experience with any person shall "
            "not be relevant on the issue of such consent or the "
            "quality of consent."
        ),
        "punishment": "N/A (evidentiary)",
        "bailable": "N/A",
        "cognizable": "N/A",
        "keywords": ["sexual offence", "character evidence", "53A",
                     "previous sexual history", "rape victim character"],
        "transition_note": "Replaces IEA 53A. The bar on character/sexual-history evidence in rape cases is statutory and absolute.",
    },
]


def get_all_documents():
    """Return BNSS + BSA combined in the same shape as bns_knowledge_base.get_all_documents()."""
    documents, metadatas, ids = [], [], []
    for section in BNSS_SECTIONS + BSA_SECTIONS:
        doc = (
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
        documents.append(doc)
        metadatas.append(meta)
        ids.append(section["id"])
    return documents, metadatas, ids
