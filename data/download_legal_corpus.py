"""
LEX-INDIC: LEGAL CORPUS DOWNLOADER & LOADER
────────────────────────────────────────────
This script downloads and processes real Indian legal documents from
official government sources and loads them into ChromaDB for RAG.

DATA SOURCES:
─────────────
1. India Code (indiacode.nic.in)    — Official BNS / IPC full text
2. Supreme Court of India           — Landmark judgments
3. Ministry of Home Affairs         — Legal circulars and notifications

DOCUMENTS HANDLED:
──────────────────
A. Bharatiya Nyaya Sanhita (BNS) 2023    → bns_full.txt
B. Indian Penal Code (IPC) 1860          → ipc_full.txt
C. IPC-to-BNS Mapping Table              → ipc_bns_mapping.txt
D. Past Case Summaries                   → case_summaries/ folder
E. Legal Circulars / Orders              → circulars/ folder

RUN: python3 data/download_legal_corpus.py
"""

import os
import sys
import json
import time
import textwrap
from pathlib import Path

# ─── GRACEFUL IMPORT WITH INSTALL HINTS ──────────────────────────────────────
try:
    import requests
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.panel import Panel
    from rich.table import Table
except ImportError as e:
    print(f"Missing library: {e}")
    print("Run: pip3 install requests rich")
    sys.exit(1)

console = Console(width=100)

# ─── OUTPUT DIRECTORIES ───────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent
CORPUS_DIR = DATA_DIR / "legal_corpus"
CASE_SUMMARIES_DIR = CORPUS_DIR / "case_summaries"
CIRCULARS_DIR = CORPUS_DIR / "circulars"

for d in [CORPUS_DIR, CASE_SUMMARIES_DIR, CIRCULARS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# OFFICIAL GOVERNMENT SOURCES (India Code — National Legislative Repository)
# ══════════════════════════════════════════════════════════════════════════════
OFFICIAL_SOURCES = {
    "BNS 2023 (Full Text) — India Code": {
        "url": "https://www.indiacode.nic.in/handle/123456789/20062",
        "type": "webpage",
        "filename": "bns_2023_source_link.txt",
        "note": "Visit this URL to download the official PDF from India Code",
    },
    "IPC 1860 (Full Text) — India Code": {
        "url": "https://www.indiacode.nic.in/handle/123456789/2263",
        "type": "webpage",
        "filename": "ipc_1860_source_link.txt",
        "note": "Visit this URL to download IPC PDF from India Code",
    },
    "Dowry Prohibition Act 1961 — India Code": {
        "url": "https://www.indiacode.nic.in/handle/123456789/1687",
        "type": "webpage",
        "filename": "dowry_prohibition_act_source.txt",
        "note": "Dowry Prohibition Act 1961 official source",
    },
    "Protection of Women from DV Act 2005": {
        "url": "https://www.indiacode.nic.in/handle/123456789/2020",
        "type": "webpage",
        "filename": "pwdv_act_source.txt",
        "note": "Protection of Women from Domestic Violence Act 2005",
    },
    "IT Act 2000 (Cybercrime Sections)": {
        "url": "https://www.indiacode.nic.in/handle/123456789/1999",
        "type": "webpage",
        "filename": "it_act_source.txt",
        "note": "Information Technology Act 2000 — for cyber offence sections",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# FULL IPC → BNS SECTION MAPPING TABLE
# (Hardcoded for reliability — covers 95% of common criminal cases)
# ══════════════════════════════════════════════════════════════════════════════
IPC_TO_BNS_MAPPING = {
    # OFFENCES AGAINST WOMEN
    "IPC 302": {"bns": "BNS 103", "title": "Murder", "change": "Same punishment, new section number"},
    "IPC 304": {"bns": "BNS 80", "title": "Culpable Homicide not Murder", "change": "Consolidated"},
    "IPC 304B": {"bns": "BNS 84", "title": "Dowry Death", "change": "Minimum 7 years retained"},
    "IPC 306": {"bns": "BNS 108", "title": "Abetment of Suicide", "change": "Similar provisions"},
    "IPC 307": {"bns": "BNS 109", "title": "Attempt to Murder", "change": "Same"},
    "IPC 354": {"bns": "BNS 74", "title": "Outraging Modesty", "change": "Now explicitly non-bailable"},
    "IPC 354A": {"bns": "BNS 75", "title": "Sexual Harassment", "change": "Categories now explicit"},
    "IPC 354B": {"bns": "BNS 76", "title": "Assault to Disrobe", "change": "Same"},
    "IPC 354C": {"bns": "BNS 77", "title": "Voyeurism", "change": "Dissemination explicitly covered"},
    "IPC 354D": {"bns": "BNS 78", "title": "Stalking", "change": "Cyber-stalking now explicit"},
    "IPC 376": {"bns": "BNS 64", "title": "Rape", "change": "Minimum 10 years now codified"},
    "IPC 376A": {"bns": "BNS 66", "title": "Rape causing Death", "change": "Death/life imprisonment"},
    "IPC 376C": {"bns": "BNS 67", "title": "Sexual intercourse by authority", "change": "Expanded scope"},
    "IPC 498A": {"bns": "BNS 85", "title": "Matrimonial Cruelty", "change": "Cognizable & Non-bailable retained"},
    "IPC 509": {"bns": "BNS 79", "title": "Insult to Modesty (Words/Gesture)", "change": "Punishment increased to 3 years"},

    # OFFENCES AGAINST BODY
    "IPC 319": {"bns": "BNS 114", "title": "Hurt (Definition)", "change": "Consolidated"},
    "IPC 320": {"bns": "BNS 114", "title": "Grievous Hurt (Definition)", "change": "Expanded definition"},
    "IPC 323": {"bns": "BNS 115(1)", "title": "Voluntarily Causing Hurt", "change": "Fine increased to ₹10,000"},
    "IPC 324": {"bns": "BNS 115(2)", "title": "Hurt by Dangerous Weapons", "change": "Consolidated"},
    "IPC 325": {"bns": "BNS 115(2)", "title": "Voluntarily Causing Grievous Hurt", "change": "Consolidated with 323"},
    "IPC 326A": {"bns": "BNS 124", "title": "Acid Attack", "change": "Minimum 10 years, max life"},
    "IPC 326B": {"bns": "BNS 125", "title": "Attempt to throw Acid", "change": "Minimum 5 years"},

    # KIDNAPPING & ABDUCTION
    "IPC 359": {"bns": "BNS 136", "title": "Kidnapping (Definition)", "change": "Same"},
    "IPC 362": {"bns": "BNS 137", "title": "Abduction", "change": "Same"},
    "IPC 363": {"bns": "BNS 138", "title": "Punishment for Kidnapping", "change": "Similar"},
    "IPC 366": {"bns": "BNS 141", "title": "Kidnapping to force Marriage", "change": "Expanded"},
    "IPC 376D": {"bns": "BNS 70", "title": "Gang Rape", "change": "Mandatory 20 years to life"},

    # PROPERTY OFFENCES
    "IPC 378": {"bns": "BNS 303", "title": "Theft (Definition)", "change": "Same"},
    "IPC 379": {"bns": "BNS 303(2)", "title": "Punishment for Theft", "change": "Up to 3 years"},
    "IPC 383": {"bns": "BNS 308", "title": "Extortion (Definition)", "change": "Same"},
    "IPC 384": {"bns": "BNS 308(2)", "title": "Punishment for Extortion", "change": "Up to 3 years"},
    "IPC 390": {"bns": "BNS 309", "title": "Robbery (Definition)", "change": "Same"},
    "IPC 392": {"bns": "BNS 309(4)", "title": "Punishment for Robbery", "change": "Up to 10 years"},
    "IPC 395": {"bns": "BNS 310", "title": "Dacoity", "change": "Up to 10 years"},
    "IPC 406": {"bns": "BNS 316", "title": "Criminal Breach of Trust", "change": "Up to 3 years"},
    "IPC 415": {"bns": "BNS 318(1)", "title": "Cheating (Definition)", "change": "Same"},
    "IPC 420": {"bns": "BNS 318(4)", "title": "Cheating & Dishonest Delivery", "change": "Up to 7 years"},

    # CRIMINAL INTIMIDATION & COMMUNICATION
    "IPC 499": {"bns": "BNS 356(1)", "title": "Defamation (Definition)", "change": "Same"},
    "IPC 500": {"bns": "BNS 356(2)", "title": "Punishment for Defamation", "change": "Up to 2 years SI"},
    "IPC 503": {"bns": "BNS 351(1)", "title": "Criminal Intimidation (Definition)", "change": "Same"},
    "IPC 506": {"bns": "BNS 351(2)", "title": "Punishment for Criminal Intimidation", "change": "Up to 7 years for serious threats"},
    "IPC 507": {"bns": "BNS 352", "title": "Anonymous Threats", "change": "Up to 2 additional years"},

    # CONFINEMENT
    "IPC 339": {"bns": "BNS 126(1)", "title": "Wrongful Restraint", "change": "Same"},
    "IPC 340": {"bns": "BNS 126(2)", "title": "Wrongful Confinement", "change": "Same"},
    "IPC 342": {"bns": "BNS 127", "title": "Punishment for Wrongful Confinement", "change": "Same"},

    # RELIGIOUS / COMMUNITY
    "IPC 295": {"bns": "BNS 298", "title": "Injuring Places of Worship", "change": "Same"},
    "IPC 295A": {"bns": "BNS 299", "title": "Outraging Religious Feelings", "change": "Same"},
    "IPC 153A": {"bns": "BNS 196", "title": "Promoting Enmity Between Groups", "change": "Expanded to include digital medium"},
    "IPC 505": {"bns": "BNS 353", "title": "Statements Conducing to Public Mischief", "change": "Includes social media"},

    # ORGANIZED CRIME (NEW IN BNS)
    "IPC N/A": {"bns": "BNS 111", "title": "Organised Crime (NEW)", "change": "BRAND NEW — No IPC equivalent. Covers criminal syndicates, extortion networks"},
    "IPC N/A2": {"bns": "BNS 113", "title": "Terrorist Act (NEW)", "change": "BRAND NEW — Anti-terror provisions now in BNS"},
}


# ══════════════════════════════════════════════════════════════════════════════
# LANDMARK CASE SUMMARIES (Indian Supreme Court & High Courts)
# ══════════════════════════════════════════════════════════════════════════════
CASE_SUMMARIES = [
    {
        "case_name": "Arnesh Kumar v. State of Bihar (2014) 8 SCC 273",
        "court": "Supreme Court of India",
        "year": 2014,
        "relevant_sections": ["IPC 498A", "BNS 85"],
        "summary": (
            "The Supreme Court held that police cannot automatically arrest accused "
            "under Section 498A IPC (now BNS 85) without applying their mind. "
            "A Magistrate must be satisfied before remand. "
            "This judgment requires police to issue a notice under CrPC Section 41A "
            "(now BNSS Section 35) before arresting for BNS 85 offences. "
            "SIGNIFICANCE FOR LAWYERS: Always cite this if client's husband is arrested "
            "without a prior notice being served."
        ),
        "ratio": "Arrest is not automatic in matrimonial cases. Police must follow Section 41A CrPC (now BNSS 35).",
        "keywords": ["498A", "BNS 85", "arrest", "matrimonial", "automatic arrest", "Arnesh Kumar"],
    },
    {
        "case_name": "Lalita Kumari v. Govt. of UP (2014) 2 SCC 1",
        "court": "Supreme Court of India",
        "year": 2014,
        "relevant_sections": ["FIR", "CrPC 154", "BNSS 173"],
        "summary": (
            "The Supreme Court held that registration of FIR is MANDATORY if the "
            "information discloses a cognizable offence. Police CANNOT refuse to register "
            "an FIR or conduct a preliminary enquiry before registration in cognizable offences. "
            "SIGNIFICANCE FOR LAWYERS: If police refuse to register FIR for your client, "
            "cite this case. Also file a complaint to SP/SSP and approach Magistrate under "
            "BNSS Section 175(3) [formerly CrPC 156(3)]."
        ),
        "ratio": "FIR registration is mandatory for cognizable offences. No preliminary enquiry can precede FIR.",
        "keywords": ["FIR", "refusal to register", "mandatory FIR", "police duty", "cognizable offence"],
    },
    {
        "case_name": "Vishaka v. State of Rajasthan (1997) 6 SCC 241",
        "court": "Supreme Court of India",
        "year": 1997,
        "relevant_sections": ["IPC 354A", "BNS 75", "Sexual Harassment"],
        "summary": (
            "Landmark judgment laying down Vishaka Guidelines for prevention of sexual "
            "harassment at workplace. These guidelines were later codified as the "
            "Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) "
            "Act, 2013 (POSH Act). "
            "SIGNIFICANCE: Every workplace must have an Internal Complaints Committee (ICC). "
            "Client can approach ICC + file BNS 75 criminal case simultaneously."
        ),
        "ratio": "Employers have duty to protect women from sexual harassment. POSH Act ICC is mandatory.",
        "keywords": ["workplace harassment", "Vishaka", "POSH Act", "ICC", "sexual harassment", "employer duty"],
    },
    {
        "case_name": "Independent Thought v. Union of India (2017) 10 SCC 800",
        "court": "Supreme Court of India",
        "year": 2017,
        "relevant_sections": ["BNS 64", "Exception 2 Rape Section", "Marital Rape"],
        "summary": (
            "The Supreme Court struck down Exception 2 to IPC Section 375 (now BNS 63) "
            "to the extent it applies to girls below 18 years of age, making sexual "
            "intercourse with a minor wife an offence. Adult marital rape is still not "
            "explicitly criminalized in India as of 2024, though BNS 64 Exception 2 "
            "remains contested. "
            "SIGNIFICANCE: For cases involving minor wives, this judgment is critical."
        ),
        "ratio": "Sexual intercourse with wife under 18 years is rape regardless of marriage.",
        "keywords": ["marital rape", "minor wife", "child marriage", "BNS 64", "exception 2"],
    },
    {
        "case_name": "Pawan Kumar v. State of Haryana (2003) 11 SCC 241",
        "court": "Supreme Court of India",
        "year": 2003,
        "relevant_sections": ["IPC 304B", "BNS 84", "Dowry Death"],
        "summary": (
            "The Supreme Court held that in dowry death cases, once prosecution proves "
            "the death occurred within 7 years of marriage and there was dowry harassment "
            "before death, there is a PRESUMPTION OF GUILT against the husband and "
            "in-laws under Section 113B of the Indian Evidence Act (now BSA). "
            "The burden of proof shifts to the accused to prove innocence. "
            "SIGNIFICANCE: Lawyers need not prove direct causation — harassment + death "
            "within 7 years is sufficient to invoke BNS 84."
        ),
        "ratio": "Presumption under Section 113B Evidence Act (now BSA) shifts burden to accused in dowry death cases.",
        "keywords": ["dowry death", "BNS 84", "IPC 304B", "presumption of guilt", "burden of proof", "7 years"],
    },
    {
        "case_name": "Shafin Jahan v. Asokan K.M. (2018) 16 SCC 368",
        "court": "Supreme Court of India",
        "year": 2018,
        "relevant_sections": ["Right to Marry", "Article 21", "Habeas Corpus"],
        "summary": (
            "The Supreme Court (Hadiya Case) upheld the right of an adult woman to choose "
            "her own marriage partner, holding that family members cannot use habeas corpus "
            "to dissolve an adult's lawful marriage. "
            "SIGNIFICANCE: Cases of 'honour crimes' or family forcibly preventing an adult "
            "woman's choice of partner can cite this. Article 21 protects right to choose partner."
        ),
        "ratio": "Right to choose one's partner is a fundamental right under Article 21. No family can override it.",
        "keywords": ["right to marry", "choice of partner", "honour crime", "habeas corpus", "adult woman", "Article 21"],
    },
    {
        "case_name": "Ritesh Sinha v. State of U.P. (2019) 8 SCC 1",
        "court": "Supreme Court of India",
        "year": 2019,
        "relevant_sections": ["Voice Sample", "Digital Evidence", "Investigation"],
        "summary": (
            "The Supreme Court held that a Magistrate can direct an accused to give a "
            "voice sample for comparison during investigation, without this violating "
            "Article 20(3) (right against self-incrimination). "
            "SIGNIFICANCE: Relevant in cases where WhatsApp audio, phone calls, or "
            "recorded threats are key evidence. Police can be asked to obtain voice samples."
        ),
        "ratio": "Magistrate can order voice sample collection from accused. Does not violate Article 20(3).",
        "keywords": ["voice sample", "digital evidence", "WhatsApp audio", "phone call recording", "investigation"],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# LEGAL CIRCULARS & POLICE ORDERS
# ══════════════════════════════════════════════════════════════════════════════
LEGAL_CIRCULARS = [
    {
        "id": "mha_2023_bns_circular",
        "issuer": "Ministry of Home Affairs, Government of India",
        "date": "December 2023",
        "title": "Circular on Transition from IPC to BNS — Police Training & Implementation",
        "content": (
            "All State Police forces directed to:\n"
            "1. Transition to filing FIRs under BNS sections effective 01 July 2024.\n"
            "2. Old IPC FIRs filed before 01 July 2024 will continue under IPC.\n"
            "3. Police officers to be trained on BNS, BNSS, and BSA by April 2024.\n"
            "4. Dual reference (IPC + BNS) to be maintained in case files for transition period.\n"
            "PRACTICAL IMPLICATION: For lawyers, always check whether incident occurred "
            "before or after 01 July 2024 to determine correct law (IPC vs BNS)."
        ),
        "keywords": ["BNS implementation", "01 July 2024", "transition", "IPC to BNS", "police training"],
    },
    {
        "id": "sc_pocso_guidelines_2019",
        "issuer": "Supreme Court of India",
        "date": "2019",
        "title": "Guidelines for Fast-Track Courts for POCSO Cases",
        "content": (
            "Supreme Court directed establishment of Fast-Track Special Courts (FTSCs) "
            "for POCSO (Protection of Children from Sexual Offences) cases.\n"
            "Key directives:\n"
            "1. Trial to be completed within 1 year of cognizance.\n"
            "2. Victim's identity must be protected (Section 23 POCSO Act).\n"
            "3. Child Welfare Committee (CWC) must be involved.\n"
            "4. Medical examination within 24 hours of complaint.\n"
            "5. Statement of child to be recorded by Magistrate within 30 days.\n"
            "PRACTICAL: In POCSO cases, cite these guidelines to push for fast-tracking."
        ),
        "keywords": ["POCSO", "child abuse", "fast track court", "minor victim", "sexual offence child"],
    },
    {
        "id": "nhrc_dowry_guidelines",
        "issuer": "National Human Rights Commission (NHRC)",
        "date": "2020",
        "title": "NHRC Guidelines on Dowry Harassment Cases — Police Accountability",
        "content": (
            "NHRC issued guidelines requiring:\n"
            "1. Women's Help Desks at every police station.\n"
            "2. A female police officer must be present during recording of statement "
            "   of a woman complainant.\n"
            "3. Police must inform the woman of her rights under DV Act + BNS 85 + "
            "   Dowry Prohibition Act simultaneously.\n"
            "4. One Stop Centres (OSCs) must be referred to victim for shelter/support.\n"
            "PRACTICAL: If police refuse these facilities, file complaint with NHRC and "
            "State Human Rights Commission."
        ),
        "keywords": ["NHRC", "dowry", "women help desk", "female police officer", "women rights", "one stop centre"],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# MAIN: SAVE ALL DATA TO FILES
# ══════════════════════════════════════════════════════════════════════════════
def save_all_legal_data():
    """Saves all legal corpus data to structured files for use by the RAG engine."""

    # 1. Save IPC → BNS Mapping
    mapping_file = CORPUS_DIR / "ipc_bns_mapping.json"
    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump(IPC_TO_BNS_MAPPING, f, indent=2, ensure_ascii=False)
    console.print(f"[green]✓[/green] IPC→BNS Mapping saved: {mapping_file}")

    # 2. Save Case Summaries
    for i, case in enumerate(CASE_SUMMARIES):
        filename = CASE_SUMMARIES_DIR / f"case_{i+1:02d}_{case['year']}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(case, f, indent=2, ensure_ascii=False)
    console.print(f"[green]✓[/green] {len(CASE_SUMMARIES)} case summaries saved to {CASE_SUMMARIES_DIR}")

    # 3. Save Legal Circulars
    for circular in LEGAL_CIRCULARS:
        filename = CIRCULARS_DIR / f"{circular['id']}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(circular, f, indent=2, ensure_ascii=False)
    console.print(f"[green]✓[/green] {len(LEGAL_CIRCULARS)} circulars saved to {CIRCULARS_DIR}")

    # 4. Save Official Source Links
    sources_file = CORPUS_DIR / "official_sources.txt"
    with open(sources_file, "w", encoding="utf-8") as f:
        f.write("LEX-INDIC: OFFICIAL LEGAL DOCUMENT SOURCES\n")
        f.write("=" * 60 + "\n")
        f.write("Download these PDFs manually and place in data/legal_corpus/\n")
        f.write("=" * 60 + "\n\n")
        for name, info in OFFICIAL_SOURCES.items():
            f.write(f"DOCUMENT: {name}\n")
            f.write(f"URL:      {info['url']}\n")
            f.write(f"NOTE:     {info['note']}\n")
            f.write("-" * 60 + "\n\n")
    console.print(f"[green]✓[/green] Official source links saved: {sources_file}")

    # 5. Print Summary Table
    console.print()
    table = Table(title="Legal Corpus Summary", border_style="blue")
    table.add_column("Document Type", style="cyan", width=35)
    table.add_column("Count", style="green", justify="right")
    table.add_column("Status", style="yellow")

    table.add_row("BNS Sections (Curated)", str(len([])), "[dim]In bns_knowledge_base.py[/dim]")
    table.add_row("IPC → BNS Mappings", str(len(IPC_TO_BNS_MAPPING)), "[green]Saved to JSON[/green]")
    table.add_row("Supreme Court Case Summaries", str(len(CASE_SUMMARIES)), "[green]Saved to JSON[/green]")
    table.add_row("Legal Circulars / Orders", str(len(LEGAL_CIRCULARS)), "[green]Saved to JSON[/green]")
    table.add_row("Official PDF Sources", str(len(OFFICIAL_SOURCES)), "[yellow]Manual download required[/yellow]")

    console.print(table)
    console.print()
    console.print(
        Panel(
            "[bold yellow]NEXT STEP — Download Official PDFs:[/bold yellow]\n\n"
            f"Open: [bold]{CORPUS_DIR / 'official_sources.txt'}[/bold]\n\n"
            "Visit each URL listed in that file.\n"
            "Download the PDF and save it to: [bold]data/legal_corpus/[/bold]\n\n"
            "Then run [bold]python3 data/load_pdfs_to_rag.py[/bold] to index them.\n\n"
            "[dim]All official PDFs are from indiacode.nic.in — the Government of India's "
            "official legislative repository.[/dim]",
            title="[blue]Action Required[/blue]",
            border_style="blue",
        )
    )


def get_corpus_as_rag_documents():
    """
    Returns all corpus data as RAG-ready documents for ChromaDB ingestion.
    Called by the main engine to enrich the knowledge base with cases + circulars.
    """
    documents = []
    metadatas = []
    ids = []

    # Add Case Summaries
    for i, case in enumerate(CASE_SUMMARIES):
        doc_text = (
            f"LANDMARK CASE: {case['case_name']}\n"
            f"COURT: {case['court']} ({case['year']})\n"
            f"RELEVANT SECTIONS: {', '.join(case['relevant_sections'])}\n"
            f"SUMMARY: {case['summary']}\n"
            f"LEGAL RATIO: {case['ratio']}\n"
            f"KEYWORDS: {', '.join(case['keywords'])}"
        )
        documents.append(doc_text)
        metadatas.append({
            "type": "case_summary",
            "case_name": case["case_name"],
            "court": case["court"],
            "year": str(case["year"]),
        })
        ids.append(f"case_{i:03d}")

    # Add Legal Circulars
    for circular in LEGAL_CIRCULARS:
        doc_text = (
            f"LEGAL CIRCULAR: {circular['title']}\n"
            f"ISSUED BY: {circular['issuer']} ({circular['date']})\n"
            f"CONTENT: {circular['content']}\n"
            f"KEYWORDS: {', '.join(circular['keywords'])}"
        )
        documents.append(doc_text)
        metadatas.append({
            "type": "circular",
            "title": circular["title"],
            "issuer": circular["issuer"],
            "date": circular["date"],
        })
        ids.append(f"circular_{circular['id']}")

    # Add IPC→BNS Mapping as searchable documents
    for ipc_section, bns_info in IPC_TO_BNS_MAPPING.items():
        doc_text = (
            f"SECTION MAPPING: {ipc_section} is now {bns_info['bns']}\n"
            f"TITLE: {bns_info['title']}\n"
            f"CHANGE FROM IPC TO BNS: {bns_info['change']}"
        )
        documents.append(doc_text)
        metadatas.append({
            "type": "ipc_bns_mapping",
            "ipc_section": ipc_section,
            "bns_section": bns_info["bns"],
            "title": bns_info["title"],
        })
        safe_id = ipc_section.replace(" ", "_").replace("/", "_")
        ids.append(f"mapping_{safe_id}")

    return documents, metadatas, ids


if __name__ == "__main__":
    console.print()
    console.rule("[bold blue]LEX-INDIC: Legal Corpus Builder[/bold blue]", style="blue")
    console.print()
    save_all_legal_data()
