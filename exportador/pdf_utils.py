import os
import tempfile
from io import BytesIO
from datetime import datetime
import ctypes
from ctypes import wintypes
from reportlab.graphics import renderPDF
from reportlab.lib.pagesizes import landscape, A3
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.graphics.shapes import Drawing, Line, Circle, String,Polygon,Rect
from reportlab.lib.utils import ImageReader

from reportlab.lib import colors
from svglib.svglib import svg2rlg

# ===========================
# Diálogo nativo de guardado
# ===========================
def elegir_ruta_guardado(nombre_sugerido="archivo.pdf"):
    try:
        class OPENFILENAMEW(ctypes.Structure):
            _fields_ = [
                ("lStructSize", wintypes.DWORD),
                ("hwndOwner", wintypes.HWND),
                ("hInstance", wintypes.HINSTANCE),
                ("lpstrFilter", wintypes.LPCWSTR),
                ("lpstrCustomFilter", wintypes.LPWSTR),
                ("nMaxCustFilter", wintypes.DWORD),
                ("nFilterIndex", wintypes.DWORD),
                ("lpstrFile", wintypes.LPWSTR),
                ("nMaxFile", wintypes.DWORD),
                ("lpstrFileTitle", wintypes.LPWSTR),
                ("nMaxFileTitle", wintypes.DWORD),
                ("lpstrInitialDir", wintypes.LPCWSTR),
                ("lpstrTitle", wintypes.LPCWSTR),
                ("Flags", wintypes.DWORD),
                ("nFileOffset", wintypes.WORD),
                ("nFileExtension", wintypes.WORD),
                ("lpstrDefExt", wintypes.LPCWSTR),
                ("lCustData", wintypes.LPARAM),
                ("lpfnHook", wintypes.LPVOID),
                ("lpTemplateName", wintypes.LPCWSTR),
                ("pvReserved", wintypes.LPVOID),
                ("dwReserved", wintypes.DWORD),
                ("FlagsEx", wintypes.DWORD),
            ]

        OFN_OVERWRITEPROMPT = 0x00000002
        buffer = ctypes.create_unicode_buffer(260)
        buffer.value = nombre_sugerido
        ofn = OPENFILENAMEW()
        ofn.lStructSize = ctypes.sizeof(ofn)
        ofn.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
        ofn.nMaxFile = 260
        ofn.lpstrFilter = "Archivos PDF\0*.pdf\0Todos los archivos\0*.*\0"
        ofn.nFilterIndex = 1
        ofn.Flags = OFN_OVERWRITEPROMPT

        if ctypes.windll.comdlg32.GetSaveFileNameW(ctypes.byref(ofn)):
            return buffer.value
    except Exception as e:
        print(f"⚠️ Error diálogo guardado: {e}")
    return None


# ===========================
# Generar PDF
# ===========================
def generar_pdf_trafo(meta, postes, red_bt=None):
    dwg = Drawing(800, 550)

    # --- Convenciones ---
    legend_x, legend_y = 600, 30  # esquina inferior derecha

    dwg.add(Rect(legend_x - 10, legend_y - 10, 180, 90, strokeColor=colors.black, fillColor=colors.whitesmoke))

    # Título
    dwg.add(String(legend_x, legend_y + 70, "CONVENCIONES", fontSize=10, fontName="Helvetica-Bold"))

    # Trafo (triángulo rojo)

    dwg.add(String(legend_x + 15, legend_y + 42, "Transformador", fontSize=8))

    # Poste (círculo verde)
    dwg.add(Circle(legend_x, legend_y + 25, 3.2, fillColor=colors.green, strokeColor=colors.black))
    dwg.add(String(legend_x + 15, legend_y + 22, "Poste BT", fontSize=8))
    dwg.add(Polygon(
        [legend_x, legend_y + 50, legend_x - 5, legend_y + 40, legend_x + 5, legend_y + 40],
        fillColor=colors.red,
        strokeColor=colors.black
    ))
    # Línea BT (azul)
    dwg.add(Line(legend_x - 5, legend_y + 5, legend_x + 5, legend_y + 5, strokeColor=colors.blue, strokeWidth=1.5))
    dwg.add(String(legend_x + 15, legend_y + 2, "Red BT", fontSize=8))
    

    print("🧠 META RECIBIDO EN PDF ===============================")
    if meta:
        for k, v in meta.items():
            print(f"  {k}: {v}")
    else:
        print("⚠️ META está vacío o None")
    print("========================================================")
    # Calcular escala y desplazamiento
    coords = []
    if postes:
        coords += [(float(p["x"]), float(p["y"])) for p in postes if p.get("x") and p.get("y")]
    if red_bt:
        for x1, y1, x2, y2 in red_bt:
            coords += [(x1, y1), (x2, y2)]

    if coords:
        xs, ys = zip(*coords)
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        ancho, alto = max_x - min_x, max_y - min_y
        escala = 550 / max(ancho, alto) if max(ancho, alto) > 0 else 1
        off_x = 400 - ((min_x + max_x) / 2) * escala
        off_y = 275 - ((min_y + max_y) / 2) * escala
    else:
        escala, off_x, off_y = 1, 400, 275

    # Líneas de red
    if red_bt:
        for x1, y1, x2, y2 in red_bt:
            dwg.add(Line(x1 * escala + off_x, y1 * escala + off_y,
                         x2 * escala + off_x, y2 * escala + off_y,
                         strokeColor=colors.blue, strokeWidth=1.1))

    # Postes
    for p in postes or []:
        x = float(p["x"]) * escala + off_x
        y = float(p["y"]) * escala + off_y
        dwg.add(Circle(x, y, 3.2, fillColor=colors.green))
        dwg.add(String(x, y - 8, str(p.get("macronorma", "")), fontSize=7, textAnchor="middle"))

    # Trafo
    codigo_trafo = str(meta.get("codigo_trafo", "")).upper()
    pos_trafo = None
    for p in postes or []:
        if str(p.get("codigo", "")).upper() == codigo_trafo:
            pos_trafo = (float(p["x"]), float(p["y"]))
            break
    if not pos_trafo and postes:
        pos_trafo = (float(postes[0]["x"]), float(postes[0]["y"]))

    if pos_trafo:
        tx, ty = pos_trafo[0] * escala + off_x, pos_trafo[1] * escala + off_y
        size = 8
        points = [
            tx, ty + size,
            tx - size, ty - size,
            tx + size, ty - size
        ]
        dwg.add(Polygon(points, fillColor=colors.red, strokeColor=colors.black))
        dwg.add(String(tx, ty - 15, codigo_trafo, fontSize=8, textAnchor="middle"))

    # Guardar SVG temporal
    tmp_svg = tempfile.NamedTemporaryFile(delete=False, suffix=".svg")
    svg_path = tmp_svg.name
    from reportlab.graphics import renderSVG
    renderSVG.drawToFile(dwg, svg_path)
    tmp_svg.close()

    # Convertir SVG a dibujo PDF
    drawing = svg2rlg(svg_path)
    os.remove(svg_path)

    # Escalar automáticamente para que nunca sobrepase el marco
    max_w, max_h = 1000, 600
    if drawing.width > max_w or drawing.height > max_h:
        factor = min(max_w / drawing.width, max_h / drawing.height)
        drawing.width *= factor
        drawing.height *= factor
        drawing.scale(factor, factor)

    # Crear PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A3))
    styles = getSampleStyleSheet()
    elements = []

    # --- Encabezado y datos del trafo ---
    titulo = f"<b>INFORME DE TRANSFORMADOR</b>"
    circuito = meta.get("circuito", "").upper()

    # Normalizar todas las claves de meta a minúsculas
    meta_norm = {k.lower(): v for k, v in meta.items()}

    # Buscar la capacidad sin importar nombre o formato
    capacidad = (
        meta_norm.get("capacidad_nominal")
        or meta_norm.get("capacidad")
        or meta_norm.get("kva")
        or "NR"
    )

    # Validar y formatear la capacidad
    if capacidad is None or str(capacidad).strip().upper() in ("", "NR", "NONE", "NULL"):
        capacidad = "NR"
    else:
        try:
            capacidad_val = float(capacidad)
            # Si es número entero, mostrar sin decimales
            capacidad = str(int(capacidad_val)) if capacidad_val.is_integer() else f"{capacidad_val:.2f}"
        except Exception:
            capacidad = str(capacidad)

    # Construir bloque de texto
    # Evitar mostrar la línea de capacidad si es "NR"
    cap_val = meta.get("capacidad")
    cap_line = ""
    if cap_val is not None and str(cap_val).strip().upper() not in ("NR", "NONE", "NULL", ""):
        cap_line = f"<b>Capacidad:</b> {cap_val} kVA<br/>"

    info = f"""
        <b>Circuito:</b> {meta.get('circuito','')}<br/>
        <b>Código TRAFO:</b> {meta.get('codigo_trafo','')}<br/>
        {cap_line}
        <b>Fecha:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}<br/>
    """

    # Añadir elementos al PDF
    elements.append(Paragraph(titulo, styles["Title"]))
    elements.append(Paragraph(info, styles["Normal"]))
    elements.append(Spacer(1, 20))
    elements.append(drawing)

    # Construir documento PDF en memoria
    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()


    # Guardar PDF donde el usuario elija
    nombre = f"trafo_{meta.get('codigo_trafo','SIN')}.pdf"
    ruta = elegir_ruta_guardado(nombre)

    # Si no se elige ruta, usar Documentos
    if not ruta:
        ruta = os.path.join(os.environ["USERPROFILE"], "Documents", nombre)

    # Si el archivo ya existe, intentar eliminarlo
    if os.path.exists(ruta):
        try:
            os.remove(ruta)
        except Exception as e:
            print(f"⚠️ No se pudo eliminar el archivo existente: {e}")
            # Guardar en ruta alternativa
            ruta = os.path.join(os.environ["USERPROFILE"], "Documents", f"trafo_{meta.get('codigo_trafo','SIN')}_nuevo.pdf")

    # Guardar el archivo
    with open(ruta, "wb") as f:
        f.write(pdf_data)

    print(f"✅ PDF generado correctamente: {ruta}")
    try:
        os.startfile(ruta)
    except Exception:
        pass
