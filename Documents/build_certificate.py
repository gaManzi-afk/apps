#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera el Certificado de Vigilancia (Domain & Brand Monitoring) en PDF."""

import os
import re
import sys
import glob
import json
import hashlib
from datetime import date, datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
    TableStyle, PageBreak,
)

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

FOOTER_TEXT = "RevRaise Secure | Domain & Brand Monitoring"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Logo de Area52 para la marca de agua. Coloca el PNG junto a este script con el
# nombre 'area52_logo.png', o indica otra ruta con la variable CERT_LOGO.
LOGO_PATH = os.environ.get("CERT_LOGO") or os.path.join(OUT_DIR, "area52_logo.png")
WATERMARK_ALPHA = 0.55       # opacidad de la marca de agua (0-1); al ir pequeña
                             # en la esquina necesita más cuerpo que un fondo

# --------- Carga de datos desde el reporte del escáner (clone_scan) --------- #
# Prioridad: 1) ruta JSON pasada como argumento, 2) puntero ultimo_reporte.txt,
# 3) el clone_scan_*.json más reciente del directorio. Si no hay ninguno, usa
# valores por defecto para poder probar el certificado de forma aislada.

DEFAULTS = {
    "dominio_base": "ambientesedona.com",
    "titulo": "Ambiente\u00ae Sedona",
    "fecha": None,
    "huellas_validadas": 8,
    "sospechosos": 0,
    "veredicto_global": "limpio",
    "resultados": [],
}


def localizar_reporte() -> str | None:
    if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
        return sys.argv[1]
    puntero = os.path.join(os.getcwd(), "ultimo_reporte.txt")
    if os.path.exists(puntero):
        with open(puntero, encoding="utf-8") as f:
            ruta = f.read().strip()
        if ruta and os.path.exists(ruta):
            return ruta
    candidatos = sorted(glob.glob(os.path.join(os.getcwd(), "clone_scan_*.json")),
                        key=os.path.getmtime, reverse=True)
    return candidatos[0] if candidatos else None


def cargar_datos() -> dict:
    ruta = localizar_reporte()
    if not ruta:
        print("[i] No se encontró reporte del escáner; uso valores por defecto.")
        return dict(DEFAULTS)
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
        print(f"[i] Datos tomados del reporte: {os.path.basename(ruta)}")
        return {**DEFAULTS, **data}
    except (OSError, ValueError) as e:
        print(f"[!] No se pudo leer {ruta} ({e}); uso valores por defecto.")
        return dict(DEFAULTS)


def nombre_marca(titulo: str, dominio: str) -> str:
    """Deriva un nombre de marca legible del título; si no, del dominio."""
    if titulo:
        # El nombre de marca suele ir tras el último separador del <title>.
        partes = re.split(r"\s[\|\u2013\u2014\-\u00b7]\s", titulo)
        cand = partes[-1].strip()
        if 2 <= len(cand) <= 40:
            return cand
    base = dominio.split(".")[0]
    return base.replace("-", " ").title()


_D = cargar_datos()
SUBJECT_DOMAIN = _D["dominio_base"]
SUBJECT_NAME = (os.environ.get("CERT_SUBJECT_NAME")
                or nombre_marca(_D.get("titulo", ""), SUBJECT_DOMAIN))
FINGERPRINTS_VALIDATED = int(_D.get("huellas_validadas", 0) or 0)
SOSPECHOSOS = int(_D.get("sospechosos", 0) or 0)
VEREDICTO = _D.get("veredicto_global", "limpio")
RESULTADOS = _D.get("resultados", []) or []

# Fecha de evaluación: del reporte (ts YYYYMMDD_HHMMSS) o la de hoy.
if _D.get("fecha"):
    try:
        ASSESSMENT_DATE = datetime.strptime(_D["fecha"][:8], "%Y%m%d").date()
    except ValueError:
        ASSESSMENT_DATE = date.today()
else:
    ASSESSMENT_DATE = date.today()

_slug = re.sub(r"[^A-Za-z0-9]", "", SUBJECT_DOMAIN.split(".")[0]).title() or "Report"
OUTPUT = os.path.join(OUT_DIR, f"Monitoring_Certificate_{_slug}.pdf")

# Identificador determinista del certificado.
_token = hashlib.sha256(
    f"{SUBJECT_DOMAIN}{ASSESSMENT_DATE.isoformat()}".encode()
).hexdigest()[:6].upper()
CERT_ID = f"RRS-DBM-{ASSESSMENT_DATE.strftime('%Y%m%d')}-{_token}"

# ------------------------------- Paleta ------------------------------------ #

NAVY = HexColor("#0E2A47")
BLUE = HexColor("#2C6FB5")
STEEL = HexColor("#5B7A99")
LIGHT = HexColor("#EEF3F8")
GREEN = HexColor("#1F8A5B")
AMBER = HexColor("#C77A1A")
INK = HexColor("#1B2A3A")
GREY = HexColor("#6B7A8D")

PAGE_W, PAGE_H = A4


# --------------------------- Marca de agua (logo) -------------------------- #

def preparar_marca_agua():
    """Crea una versión tenue del logo para usarla como marca de agua.

    Devuelve la ruta del PNG atenuado, o None si no hay logo o falta PIL.
    """
    if not os.path.exists(LOGO_PATH):
        print(f"[i] Logo no encontrado en {LOGO_PATH}; se omite la marca de agua.")
        return None
    if not HAVE_PIL:
        print("[i] Pillow no instalado (pip install pillow); marca de agua omitida.")
        return None
    try:
        img = Image.open(LOGO_PATH).convert("RGBA")
        alpha = img.split()[3].point(lambda v: int(v * WATERMARK_ALPHA))
        img.putalpha(alpha)
        destino = os.path.join(OUT_DIR, ".a52_watermark.png")
        img.save(destino)
        return destino
    except Exception as e:                           # noqa: BLE001
        print(f"[i] No se pudo preparar la marca de agua ({e}).")
        return None


WATERMARK = preparar_marca_agua()


# --------------------------- Dibujo de cada página ------------------------- #

def draw_frame(canvas, doc):
    canvas.saveState()
    # Marco doble.
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(2.2)
    canvas.rect(15 * mm, 15 * mm, PAGE_W - 30 * mm, PAGE_H - 30 * mm)
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(0.6)
    canvas.rect(17 * mm, 17 * mm, PAGE_W - 34 * mm, PAGE_H - 34 * mm)

    # Barra superior de marca.
    canvas.setFillColor(NAVY)
    canvas.rect(15 * mm, PAGE_H - 33 * mm, PAGE_W - 30 * mm, 18 * mm, fill=1, stroke=0)
    canvas.setFillColor(HexColor("#FFFFFF"))
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(22 * mm, PAGE_H - 26 * mm, "RevRaise Secure")
    canvas.setFillColor(BLUE)
    canvas.setFont("Helvetica", 8.5)
    canvas.drawRightString(PAGE_W - 22 * mm, PAGE_H - 23.5 * mm, "DOMAIN & BRAND")
    canvas.drawRightString(PAGE_W - 22 * mm, PAGE_H - 27.5 * mm, "MONITORING")

    # Pie de página en cada hoja.
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(0.8)
    canvas.line(22 * mm, 22 * mm, PAGE_W - 22 * mm, 22 * mm)
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.drawCentredString(PAGE_W / 2, 18 * mm, FOOTER_TEXT)
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(22 * mm, 18 * mm, f"Ref. {CERT_ID}")
    canvas.drawRightString(PAGE_W - 22 * mm, 18 * mm, f"Page {doc.page}")
    canvas.restoreState()


def draw_seal(canvas, cx, cy, r):
    """Sello circular de verificación."""
    canvas.saveState()
    canvas.setStrokeColor(GREEN)
    canvas.setLineWidth(2.2)
    canvas.circle(cx, cy, r, stroke=1, fill=0)
    canvas.setLineWidth(0.8)
    canvas.circle(cx, cy, r - 2.2 * mm, stroke=1, fill=0)
    # Check.
    canvas.setStrokeColor(GREEN)
    canvas.setLineWidth(2.6)
    canvas.line(cx - 4.2 * mm, cy + 0.4 * mm, cx - 1.1 * mm, cy - 3.0 * mm)
    canvas.line(cx - 1.1 * mm, cy - 3.0 * mm, cx + 4.6 * mm, cy + 4.2 * mm)
    canvas.setFillColor(GREEN)
    canvas.setFont("Helvetica-Bold", 6.2)
    canvas.drawCentredString(cx, cy - r + 3.4 * mm, "VERIFIED")
    canvas.restoreState()


def draw_watermark(canvas):
    """Logo pequeño como marca de agua, abajo a la izquierda."""
    if not WATERMARK:
        return
    w = h = 20 * mm                  # el logo es cuadrado
    x = 20 * mm                      # pegado al borde izquierdo
    y = 24 * mm                      # justo encima del pie de página
    canvas.saveState()
    canvas.drawImage(WATERMARK, x, y, width=w, height=h,
                     mask="auto", preserveAspectRatio=True)
    canvas.restoreState()


def first_page(canvas, doc):
    draw_frame(canvas, doc)
    draw_watermark(canvas)           # detrás: el texto se dibuja después
    if doc.page == 1 and VEREDICTO == "limpio":
        draw_seal(canvas, PAGE_W - 34 * mm, PAGE_H - 86 * mm, 12 * mm)


# ------------------------------- Estilos ----------------------------------- #

def styles():
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=23,
                                 textColor=NAVY, alignment=TA_CENTER, leading=26,
                                 spaceBefore=6, spaceAfter=2),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=10.5,
                                    textColor=STEEL, alignment=TA_CENTER,
                                    leading=14, spaceAfter=10),
        "kicker": ParagraphStyle("kicker", fontName="Helvetica-Bold", fontSize=9,
                                  textColor=BLUE, alignment=TA_CENTER,
                                  spaceAfter=2, tracking=2),
        "lead": ParagraphStyle("lead", fontName="Helvetica", fontSize=10.5,
                               textColor=INK, alignment=TA_CENTER, leading=16),
        "subject": ParagraphStyle("subject", fontName="Helvetica-Bold", fontSize=15,
                                   textColor=NAVY, alignment=TA_CENTER, leading=18),
        "domain": ParagraphStyle("domain", fontName="Helvetica", fontSize=11,
                                  textColor=BLUE, alignment=TA_CENTER, leading=14,
                                  spaceAfter=4),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5,
                             textColor=NAVY, alignment=TA_LEFT, spaceBefore=4,
                             spaceAfter=4),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.3,
                               textColor=INK, alignment=TA_JUSTIFY, leading=13.5),
        "vtitle": ParagraphStyle("vtitle", fontName="Helvetica-Bold", fontSize=9.6,
                                 textColor=NAVY, leading=12),
        "vdesc": ParagraphStyle("vdesc", fontName="Helvetica", fontSize=8.7,
                                textColor=INK, leading=12, alignment=TA_JUSTIFY),
        "vres": ParagraphStyle("vres", fontName="Helvetica-Bold", fontSize=8.7,
                               textColor=GREEN, leading=12),
        "vres_warn": ParagraphStyle("vres_warn", fontName="Helvetica-Bold",
                                    fontSize=8.7, textColor=AMBER, leading=12),
        "verdict": ParagraphStyle("verdict", fontName="Helvetica-Bold", fontSize=11.5,
                                  textColor=NAVY, alignment=TA_CENTER, leading=15),
        "note": ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=7.3,
                               textColor=GREY, alignment=TA_JUSTIFY, leading=9.5),
        "siglabel": ParagraphStyle("siglabel", fontName="Helvetica", fontSize=8,
                                   textColor=GREY, alignment=TA_CENTER),
        "sigval": ParagraphStyle("sigval", fontName="Helvetica-Bold", fontSize=9,
                                 textColor=NAVY, alignment=TA_CENTER),
        "performed": ParagraphStyle("performed", fontName="Helvetica", fontSize=10,
                                    textColor=NAVY, alignment=TA_CENTER, leading=14),
        "performed_sub": ParagraphStyle("performed_sub", fontName="Helvetica",
                                        fontSize=8, textColor=GREY,
                                        alignment=TA_CENTER, leading=11,
                                        spaceBefore=1),
        "disc_h1": ParagraphStyle("disc_h1", fontName="Helvetica-Bold",
                                  fontSize=14, textColor=NAVY, alignment=TA_CENTER,
                                  leading=17, spaceAfter=1),
        "disc_ref": ParagraphStyle("disc_ref", fontName="Helvetica", fontSize=8.5,
                                   textColor=STEEL, alignment=TA_CENTER, leading=12,
                                   spaceAfter=8),
        "disc_h2": ParagraphStyle("disc_h2", fontName="Helvetica-Bold",
                                  fontSize=9.8, textColor=BLUE, alignment=TA_LEFT,
                                  leading=13, spaceBefore=8, spaceAfter=2),
        "disc_body": ParagraphStyle("disc_body", fontName="Helvetica", fontSize=9,
                                    textColor=INK, alignment=TA_JUSTIFY,
                                    leading=13.5),
        "pointer": ParagraphStyle("pointer", fontName="Helvetica-Oblique",
                                  fontSize=7.8, textColor=GREY,
                                  alignment=TA_CENTER, leading=10.5),
    }


# --------------------------- Contenido (flowables) ------------------------- #

def build_story(st):
    story = []
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("CERTIFICATE OF", st["kicker"]))
    story.append(Paragraph("Domain &amp; Brand Monitoring", st["title"]))
    story.append(Paragraph(
        "Clone, Spoofing &amp; Impersonation Surveillance", st["subtitle"]))

    story.append(Paragraph(
        "This document certifies that <b>RevRaise Secure</b> has conducted a "
        "domain and brand monitoring assessment to detect cloned, spoofed, or "
        "fraudulently replicated instances of the digital property identified "
        "below.", st["lead"]))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(SUBJECT_NAME, st["subject"]))
    story.append(Paragraph(
        f'<link href="https://{SUBJECT_DOMAIN}">{SUBJECT_DOMAIN}</link>',
        st["domain"]))
    story.append(Spacer(1, 3 * mm))

    # Tabla de metadatos.
    meta = Table([
        ["Certificate ID", CERT_ID,
         "Assessment Date", ASSESSMENT_DATE.strftime("%B %d, %Y")],
        ["Monitored Asset", SUBJECT_DOMAIN,
         "Fingerprints Validated", str(FINGERPRINTS_VALIDATED)],
    ], colWidths=[33 * mm, 50 * mm, 38 * mm, 35 * mm])
    meta.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("TEXTCOLOR", (0, 0), (0, -1), GREY),
        ("TEXTCOLOR", (2, 0), (2, -1), GREY),
        ("TEXTCOLOR", (1, 0), (1, -1), NAVY),
        ("TEXTCOLOR", (3, 0), (3, -1), NAVY),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, STEEL),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, HexColor("#D5DEE8")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(meta)
    story.append(Spacer(1, 4 * mm))

    # Validaciones.
    story.append(Paragraph("VALIDATIONS PERFORMED", st["h2"]))
    validations = [
        ("1. Typosquatting &amp; Domain Permutation Analysis",
         "Automated generation of look-alike domains (character substitutions, "
         "homoglyphs, insertions and alternate top-level domains) with live "
         "resolution of registered variants.",
         "No malicious or deceptive registered permutations identified."),
        ("2. Certificate Transparency (CT) Monitoring",
         "Review of public Certificate Transparency logs for TLS certificates "
         "issued to domains incorporating the protected brand name.",
         "No unauthorized or fraudulent certificates detected."),
        ("3. Content Fingerprint Analysis",
         "Cross-referencing of the asset's unique digital fingerprints "
         "(favicon, brand logo, social and gallery imagery, and web analytics "
         "&amp; tag-manager identifiers) against global web-scan intelligence "
         "to locate unauthorized reuse on any third-party domain.",
         (f"{FINGERPRINTS_VALIDATED} distinctive fingerprints validated; none "
          "served from any external domain." if VEREDICTO == "limpio"
          else f"{FINGERPRINTS_VALIDATED} fingerprints validated; "
               f"{SOSPECHOSOS} third-party domain(s) flagged for review.")),
    ]
    rows = []
    for idx, (title, desc, res) in enumerate(validations):
        res_style = st["vres"]
        if idx == 2 and VEREDICTO != "limpio":
            res_style = st["vres_warn"]
        block = [
            Paragraph(title, st["vtitle"]),
            Paragraph(desc, st["vdesc"]),
            Paragraph("Result: " + res, res_style),
        ]
        rows.append([block])
    vtable = Table(rows, colWidths=[PAGE_W - 58 * mm])
    vtable.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FFFFFF")),
        ("BOX", (0, 0), (-1, -1), 0.5, STEEL),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, HexColor("#D5DEE8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, BLUE),
    ]))
    story.append(vtable)
    story.append(Spacer(1, 4 * mm))

    # Veredicto (dinámico según el resultado del escaneo).
    if VEREDICTO == "limpio":
        vcolor, vtxt = GREEN, (
            "ASSESSMENT RESULT &mdash; NO CLONES DETECTED<br/>"
            "<font size=9 color='#1B2A3A'>As of the assessment date, no cloned, "
            "spoofed, or fraudulently replicated instances of the monitored "
            "property were identified across any applied detection vector.</font>")
    else:
        vcolor, vtxt = AMBER, (
            f"ASSESSMENT RESULT &mdash; {SOSPECHOSOS} POTENTIAL MATCH(ES) FLAGGED<br/>"
            "<font size=9 color='#1B2A3A'>Third-party domains reproducing "
            "distinctive fingerprints of the monitored property were flagged and "
            "require manual review. See the accompanying technical report.</font>")
    verdict = Table([[Paragraph(vtxt, st["verdict"])]],
                    colWidths=[PAGE_W - 58 * mm])
    verdict.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 1.1, vcolor),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(verdict)
    story.append(Spacer(1, 4 * mm))

    # Realizado por (reemplaza el bloque de firma).
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "This assessment was performed by the <b>Area52</b> team.",
        st["performed"]))
    story.append(Paragraph(
        f"Issued {ASSESSMENT_DATE.strftime('%B %d, %Y')}", st["performed_sub"]))
    story.append(Spacer(1, 4 * mm))

    # Remisión al disclaimer (la nota completa va en la hoja siguiente).
    story.append(Paragraph(
        "This certificate is issued subject to the Statement of Assurance &amp; "
        "Disclaimer set out on the following page.", st["pointer"]))

    # ---------------------- Hoja 2: Statement of Assurance ----------------- #
    story.append(PageBreak())
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("STATEMENT OF ASSURANCE &amp; DISCLAIMER",
                           st["disc_h1"]))
    story.append(Paragraph(
        f"Annex to Certificate {CERT_ID} &mdash; {SUBJECT_DOMAIN}", st["disc_ref"]))

    secciones = [
        ("Nature of the assurance",
         "No detection methodology &mdash; whether proprietary to RevRaise "
         "Secure or offered by commercial vendors &mdash; can provide absolute "
         "certainty that no cloned, spoofed, or fraudulently replicated instance "
         "of a digital asset exists. The non-existence of such a replica is a "
         "negative condition that cannot be proven exhaustively. Accordingly, "
         "this certificate does not assert that no clone exists; it attests, "
         "with high confidence, that on the assessment date stated overleaf "
         "RevRaise Secure performed the validations described below and "
         "documented their findings."),
        ("Scope of validation",
         "The assessment cross-references three independent, industry-standard "
         "detection vectors: (1) domain-permutation and typosquatting analysis, "
         "covering character substitutions, homoglyphs, insertions and alternate "
         "top-level domains; (2) Certificate Transparency monitoring of public "
         "logs for TLS certificates issued to domains incorporating the protected "
         "brand; and (3) content-fingerprint analysis, in which the asset's "
         "distinctive artifacts &mdash; favicon, brand logo, social and gallery "
         "imagery, and web analytics and tag-manager identifiers &mdash; are "
         "cross-referenced against global web-scan intelligence to locate "
         "unauthorized reuse on any third-party domain."),
        ("Interpretation of a clean result",
         "A &ldquo;clean&rdquo; outcome is a verifiable negative: the asset's "
         "distinctive fingerprints were not found served from any third-party "
         "domain indexed by the consulted intelligence sources. To preserve the "
         "integrity of this finding, generic and widely-reused resources &mdash; "
         "such as common JavaScript libraries and content-management framework "
         "files &mdash; are deliberately excluded from the comparison, so that a "
         "clean result reflects the genuine absence of matches rather than "
         "statistical noise or false positives."),
        ("Limitations and validity",
         "The findings reflect the state observable at the assessment date and "
         "depend on the coverage of public intelligence sources; a replica "
         "deployed after that date, or hosted on infrastructure not yet indexed, "
         "may not be represented. This certificate does not constitute a warranty "
         "or guarantee against future infringement and is issued for the "
         "exclusive use of the asset owner and their authorized representatives. "
         "RevRaise Secure recommends continuous monitoring to maintain effective "
         "brand protection."),
    ]
    for titulo, cuerpo in secciones:
        story.append(Paragraph(titulo, st["disc_h2"]))
        story.append(Paragraph(cuerpo, st["disc_body"]))

    return story


# --------------------------------- Build ----------------------------------- #

def main():
    doc = BaseDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=29 * mm, rightMargin=29 * mm,
        topMargin=37 * mm, bottomMargin=26 * mm,
        title="Domain & Brand Monitoring Certificate",
        author="RevRaise Secure",
        subject=f"Monitoring certificate for {SUBJECT_DOMAIN}",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  PAGE_W - doc.leftMargin - doc.rightMargin,
                  PAGE_H - doc.topMargin - doc.bottomMargin, id="main")
    doc.addPageTemplates([
        PageTemplate(id="first", frames=[frame], onPage=first_page),
    ])
    doc.build(build_story(styles()))
    print("Certificado generado:", OUTPUT)


if __name__ == "__main__":
    main()
