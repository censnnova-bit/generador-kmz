from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
import os
import simplekml
from datetime import datetime

from .pdf_utils import generar_pdf_trafo
from .queries import queries
from .Main_Ui import entidades_config
from .core import (
    obtener_circuitos,
    obtener_trafos_por_circuito,
    obtener_trafos,
    exportar_kmz_por_trafo,
    exportar_kmz_puntos,
    exportar_kmz_lineas,
    ejecutar_consulta
)


# ============================================================
# 🔹 API: Listado de circuitos
# ============================================================
def api_circuitos(request):
    regional = request.GET.get("regional")
    if not regional:
        return JsonResponse({"error": "Falta regional"}, status=400)
    circuitos = obtener_circuitos(regional)
    return JsonResponse({"circuitos": circuitos})


# ============================================================
# 🔹 API: Listado de trafos por circuito
# ============================================================
def api_trafos(request):
    circuito = request.GET.get("circuito")
    regional = request.GET.get("regional")
    if not circuito or not regional:
        return JsonResponse({"error": "Faltan datos"}, status=400)
    datos, _ = obtener_trafos_por_circuito(circuito, regional)
    trafos = [str(row[0]) for row in datos]
    return JsonResponse({"trafos": trafos})


# ============================================================
# 🔹 Formulario HTML principal
# ============================================================
def formulario_kmz(request):
    return render(request, "formulario_kmz.html")


# ============================================================
# 🔹 Generar KMZ por transformador
# ============================================================
def generar_kmz_por_trafo(request):
    codigo_trafo = request.GET.get("codigo_trafo")
    circuito = request.GET.get("circuito")
    regional = request.GET.get("regional")

    if not codigo_trafo or not circuito or not regional:
        return HttpResponse("❌ Faltan parámetros para generar el KMZ", status=400)

    ruta_kmz = f"/tmp/TRAFO_{codigo_trafo}.kmz"
    estilos = {
        "TRAFOS": entidades_config.get("TRAFOS", {}).get("estilo", {}),
        "POSTES_BT_BY_TRAFO": entidades_config.get("POSTES_BT_BY_TRAFO", {}).get("estilo", {}),
        "RED_BT_BY_TRAFO": entidades_config.get("RED_BT_BY_TRAFO", {}).get("estilo", {}),
    }

    resultado = exportar_kmz_por_trafo(
        salida=ruta_kmz,
        codigo_trafo=codigo_trafo,
        circuito=circuito,
        estilos=estilos,
        entidades_config=entidades_config,
        regional=regional
    )

    if resultado and os.path.exists(ruta_kmz):
        with open(ruta_kmz, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.google-earth.kmz")
            response["Content-Disposition"] = f'attachment; filename="TRAFO_{codigo_trafo}.kmz"'
            return response
    return HttpResponse("❌ Error generando el KMZ del trafo", status=500)


# ============================================================
# 🔹 Generar KMZ total (todas las entidades)
# ============================================================
def generar_kmz_total(request):
    circuito = request.GET.get("circuito")
    regional = request.GET.get("regional")
    nombre_kmz = request.GET.get("nombre_kmz")
    entidades = request.GET.getlist("entidades")

    color_red_mt = request.GET.get("color_red_mt", "#0000FF")
    color_red_bt = request.GET.get("color_red_bt", "#00FF00")

    if not circuito or not regional or not nombre_kmz or not entidades:
        return HttpResponse("❌ Faltan parámetros para generar el KMZ total", status=400)

    salida = os.path.join("/tmp", f"{nombre_kmz}.kmz")
    kml = simplekml.Kml()
    usar_altura = False

    for entidad in entidades:
        estilo = entidades_config.get(entidad, {}).get("estilo", {}).copy()
        tipo = estilo.get("tipo", "punto")

        # 🎨 Colores personalizados
        if entidad == "RED_MT":
            estilo["color"] = color_red_mt
        elif entidad == "RED_BT":
            estilo["color"] = color_red_bt

        try:
            # 🚩 Caso especial: incluir TRAFOS correctamente
            if entidad == "TRAFOS":
                exportar_kmz_puntos(
                    circuito=circuito,
                    entidad="TRAFOS",
                    estilo=estilo,
                    entidades_config=entidades_config,
                    regional=regional,
                    kml=kml
                )
                continue

            # 🚀 Exportar líneas o puntos
            if tipo == "linea":
                exportar_kmz_lineas(
                    entidad=entidad,
                    circuito=circuito,
                    regional=regional,
                    estilo=estilo,
                    usar_altura=usar_altura,
                    entidades_config=entidades_config,
                    kml=kml
                )
            else:
                exportar_kmz_puntos(
                    entidad=entidad,
                    circuito=circuito,
                    regional=regional,
                    estilo=estilo,
                    entidades_config=entidades_config,
                    kml=kml
                )
        except Exception as e:
            print(f"❌ Error exportando {entidad}: {e}")

    try:
        kml.savekmz(salida)
        with open(salida, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.google-earth.kmz")
            response["Content-Disposition"] = f'attachment; filename="{nombre_kmz}.kmz"'
            return response
    except Exception as e:
        return HttpResponse(f"❌ Error guardando KMZ: {e}", status=500)


# ============================================================
# 🔹 Generar PDF del trafo
# ============================================================
def generar_pdf_trafo_view(request):
    regional = request.GET.get("regional")
    circuito = request.GET.get("circuito")
    codigo_trafo = request.GET.get("codigo_trafo")

    if not all([regional, circuito, codigo_trafo]):
        return HttpResponse("❌ Faltan parámetros", status=400)

    # verificar existencia
    trafos = obtener_trafos(circuito, regional)
    if codigo_trafo not in trafos:
        return HttpResponse("❌ No se encontró el trafo", status=404)

    # === CAPACIDAD ===
    capacidad = "NR"
    try:
        sql = queries["TRAFOS_POR_CIRCUITO_PDF"]
        params = {"circuito": circuito, "regional": regional}
        datos, columnas = ejecutar_consulta(sql, params)
        for fila in datos:
            # columnas vienen en la lista 'columnas'
            # adaptamos índices si tu ejecutar_consulta devuelve (rows, cols)
            try:
                idx_codigo = columnas.index("CODIGO_TRAFO")
                idx_cap = columnas.index("CAPACIDAD_NOMINAL")
            except ValueError:
                # si las columnas tienen otra capitalización, normalizamos:
                lower_cols = [c.lower() for c in columnas]
                idx_codigo = lower_cols.index("codigo_trafo") if "codigo_trafo" in lower_cols else None
                idx_cap = lower_cols.index("capacidad_nominal") if "capacidad_nominal" in lower_cols else None

            if idx_codigo is not None and idx_cap is not None:
                if str(fila[idx_codigo]).upper() == codigo_trafo.upper():
                    capacidad = fila[idx_cap]
                    break
    except Exception as e:
        print(f"⚠️ Error obteniendo capacidad del trafo: {e}")

    meta = {
        "circuito": circuito,
        "codigo_trafo": codigo_trafo,
        "capacidad": capacidad if capacidad else "NR",
        "usuario": request.user.username if request.user.is_authenticated else "Anonimo"
    }

    print(f"📊 META FINAL PDF: {meta}")

    # === POSTES Y RED BT ===
    sql_postes = queries["POSTES_BT_BY_TRAFO"]
    postes_data, _ = ejecutar_consulta(sql_postes, {"codigo_trafo": codigo_trafo, "regional": regional})
    postes = []
    for p in postes_data:
        # intento robusto: coger primer campo como codigo y últimas dos columnas como lon/lat
        try:
            codigo = p[0]
            macronorma = p[3]
            lon = float(p[-2])
            lat = float(p[-1])
            postes.append({"codigo": codigo, "macronorma": macronorma, "x": lon, "y": lat})
        except Exception:
            continue

    sql_red = queries["RED_BT_BY_TRAFO"]
    red_data, _ = ejecutar_consulta(sql_red, {"codigo_trafo": codigo_trafo, "regional": regional})
    red_bt = []
    for r in red_data:
        try:
            red_bt.append((float(r[-4]), float(r[-3]), float(r[-2]), float(r[-1])))
        except Exception:
            continue

    # === GENERAR PDF ===
    pdf_bytes = generar_pdf_trafo(meta, postes, red_bt)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="trafo_{codigo_trafo}.pdf"'
    return response
