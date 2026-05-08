# coding: utf-8
import os
import re
import sys
import simplekml
import oracledb
import traceback
from xml.sax.saxutils import escape
from dotenv import load_dotenv
from .queries import queries


if getattr(sys, "frozen", False):
    _APP_ROOT = os.path.dirname(sys.executable)
else:
    _APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_APP_ROOT, ".env"))

print("✅ Iniciando KMZ Generator...")
print("✅ Oracle oracledb en modo thin (sin Instant Client nativo).")


# -----------------------------
# Config / util
# -----------------------------
def kml_color(hex_color):
    """Recibe '#RRGGBB' o 'RRGGBB' y devuelve formato KML 'AABBGGRR' (alpha ff)."""
    try:
        if not hex_color:
            return "ff0000ff"
        s = hex_color.lstrip("#")
        if len(s) == 3:
            s = ''.join([c*2 for c in s])
        if len(s) != 6:
            return "ff0000ff"
        r, g, b = s[0:2], s[2:4], s[4:6]
        return f"ff{b}{g}{r}"
    except Exception:
        return "ff0000ff"

def limpiar_texto_xml(texto):
    try:
        if texto is None:
            return ""
        texto = str(texto)
        texto = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\xA0-\uFFFF]", "", texto)
        return escape(texto)
    except Exception:
        return ""

def limpiar_nombre(nombre):
    return re.sub(r'[\\/*?:"<>|]', "_", nombre)

# -----------------------------
# Oracle helpers

def conectar_oracle():
    host = os.environ.get("ORACLE_HOST")
    port = os.environ.get("ORACLE_PORT", "1521")
    service = os.environ.get("ORACLE_SERVICE_NAME")
    user = os.environ.get("ORACLE_USER")
    password = os.environ.get("ORACLE_PASSWORD")
    missing = [
        name
        for name, val in (
            ("ORACLE_HOST", host),
            ("ORACLE_SERVICE_NAME", service),
            ("ORACLE_USER", user),
            ("ORACLE_PASSWORD", password),
        )
        if not val
    ]
    if missing:
        raise RuntimeError(
            "Faltan variables de entorno Oracle: %s (defínalas en .env)"
            % ", ".join(missing)
        )
    dsn = oracledb.makedsn(host, int(port), service_name=service)
    return oracledb.connect(user=user, password=password, dsn=dsn)

def ejecutar_consulta(sql, params=None):
    """
    Ejecuta una consulta SQL en Oracle y retorna (datos, columnas).
    """
    try:
        conn = conectar_oracle()
        cur = conn.cursor()
        cur.execute(sql, params or {})
        datos = cur.fetchall()
        columnas = [desc[0] for desc in cur.description]
        cur.close()
        conn.close()
        return datos, columnas
    except Exception as e:
        print(f"❌ Error en ejecutar_consulta: {e}")
        traceback.print_exc()
        return [], []

def obtener_datos(entidad, circuito=None, regional=None, codigo_trafo=None):
    """
    Usa el diccionario queries para ejecutar la consulta correspondiente.
    Devuelve (datos, columnas)
    """
    try:
        sql = queries.get(entidad)
        if sql is None:
            print(f"⚠ Consulta no encontrada para entidad {entidad}")
            return [], []
        params = {}
        if circuito is not None:
            params["circuito"] = circuito
        if regional is not None:
            params["regional"] = regional
        if codigo_trafo is not None:
            params["codigo_trafo"] = codigo_trafo
        return ejecutar_consulta(sql, params)
    except Exception as e:
        print(f"❌ Error consultando datos de {entidad}: {e}")
        traceback.print_exc()
        return [], []

# -----------------------------
# Helpers para columnas/coordenadas
# -----------------------------
def find_col_index(cols, candidates):
    """Busca en cols (lista de nombres) la primera coincidencia en candidates (lista) y devuelve índice o None."""
    up = [c.upper() for c in cols]
    for cand in candidates:
        try:
            i = up.index(cand.upper())
            return i
        except ValueError:
            continue
    return None

def obtener_lon_lat_desde_fila(cols, fila):
    """
    Intenta encontrar lon/lat en la fila buscando columnas comunes.
    Retorna (lon, lat) o (None, None) si no encuentra.
    """
    # candidatos de lon, lat
    lon_candidates = ["COOR_GPS_LON", "COOR_X", "LON1", "LON", "X", "COOR_X"]
    lat_candidates = ["COOR_GPS_LAT", "COOR_Y", "LAT1", "LAT", "Y", "COOR_Y"]

    lon_idx = find_col_index(cols, lon_candidates)
    lat_idx = find_col_index(cols, lat_candidates)
    if lon_idx is not None and lat_idx is not None:
        try:
            lon = float(fila[lon_idx])
            lat = float(fila[lat_idx])
            return lon, lat
        except Exception:
            return None, None
    # fallback: si están al final (muchos queries antiguos)
    try:
        lon = float(fila[-2])
        lat = float(fila[-1])
        return lon, lat
    except Exception:
        return None, None

def obtener_coords_linea(cols, fila):
    """
    Busca LON1/LAT1/LON2/LAT2 u homólogos (case-insensitive sobre nombres de columna Oracle).
    Retorna tuple (lon1, lat1, lon2, lat2) o (None,)*4
    """
    lon1_idx = find_col_index(cols, ["LON1", "COOR_X1", "X1"])
    lat1_idx = find_col_index(cols, ["LAT1", "COOR_Y1", "Y1"])
    lon2_idx = find_col_index(cols, ["LON2", "COOR_X2", "X2"])
    lat2_idx = find_col_index(cols, ["LAT2", "COOR_Y2", "Y2"])

    if all(idx is not None for idx in (lon1_idx, lat1_idx, lon2_idx, lat2_idx)):
        try:
            return float(fila[lon1_idx]), float(fila[lat1_idx]), float(fila[lon2_idx]), float(fila[lat2_idx])
        except Exception:
            return (None, None, None, None)

    # fallback: si las últimas 4 columnas son coords (consultas tipo RED_* con GetOrdinateValue al final)
    try:
        lon1 = float(fila[-4])
        lat1 = float(fila[-3])
        lon2 = float(fila[-2])
        lat2 = float(fila[-1])
        return lon1, lat1, lon2, lat2
    except Exception:
        return (None, None, None, None)

# -----------------------------
# Exportadores genéricos
# -----------------------------
def exportar_kmz_puntos(entidad, circuito, regional, estilo, entidades_config, kml, codigo_trafo=None):
    """Genera puntos en el KML para la entidad dada. Usa obtener_datos y entidades_config para etiqueta/íconos."""
    datos, cols = obtener_datos(entidad, circuito, regional, codigo_trafo)
    if not datos:
        print(f"⚠ No hay datos para {entidad} (circuito={circuito}, trafo={codigo_trafo})")
        return

    folder = kml.newfolder(name=entidad)
    etiqueta = entidades_config.get(entidad, {}).get("etiqueta")

    for fila in datos:
        try:
            lon, lat = obtener_lon_lat_desde_fila(cols, fila)
            if lon is None or lat is None:
                print(f"⚠ No se pudieron obtener coordenadas para fila (entidad {entidad}): {fila}")
                continue

            name = ""
            if etiqueta:
                # buscar índice de etiqueta en cols
                idx = find_col_index(cols, [etiqueta])
                if idx is not None:
                    name = limpiar_texto_xml(fila[idx]) if fila[idx] is not None else ""

            pnt = folder.newpoint(name=name, coords=[(lon, lat)])

            # estilo: preferir icon_href del entidades_config si existe
            estilo_cfg = entidades_config.get(entidad, {}).get("estilo", {}) or {}
            icon_href = estilo.get("icon_href") if estilo else estilo_cfg.get("icon_href")
            scale = estilo.get("scale", estilo_cfg.get("scale", 1.0)) if isinstance(estilo, dict) else estilo_cfg.get("scale", 1.0)
            color = estilo.get("color", estilo_cfg.get("color")) if isinstance(estilo, dict) else estilo_cfg.get("color")

            if icon_href and os.path.exists(icon_href):
                pnt.style.iconstyle.icon.href = icon_href
                pnt.style.iconstyle.scale = scale
            else:
                # si no hay icono, ajustar color/scale si existen
                if color:
                    pnt.style.iconstyle.color = kml_color(color)
                pnt.style.iconstyle.scale = scale

            # extended data (todos los campos)
            for i, campo in enumerate(cols):
                try:
                    pnt.extendeddata.newdata(campo, limpiar_texto_xml(fila[i]))
                except Exception:
                    # seguir si algún campo falla
                    pass

        except Exception as e:
            print(f"⚠ Error exportando punto {entidad} fila {fila}: {e}")
            traceback.print_exc()

def exportar_kmz_lineas(entidad, circuito, regional, estilo, usar_altura, entidades_config, kml, codigo_trafo=None):
    datos, cols = obtener_datos(entidad, circuito, regional, codigo_trafo)
    if not datos:
        print(f"⚠ No hay datos para {entidad} (circuito={circuito}, trafo={codigo_trafo})")
        return

    folder = kml.newfolder(name=entidad)

    for fila in datos:
        try:
            lon1, lat1, lon2, lat2 = obtener_coords_linea(cols, fila)
            if None in (lon1, lat1, lon2, lat2):
                print(f"⚠ No se pudieron obtener coords de línea para fila: {fila}")
                continue

            z = 50 if usar_altura else 0
            line = folder.newlinestring(coords=[(lon1, lat1, z), (lon2, lat2, z)])
            line.altitudemode = simplekml.AltitudeMode.relativetoground if usar_altura else simplekml.AltitudeMode.clamptoground
            line.extrude = usar_altura
            if not usar_altura:
                line.tessellate = 1

            etiqueta = entidades_config.get(entidad, {}).get("etiqueta")
            if etiqueta:
                idx = find_col_index(cols, [etiqueta])
                if idx is not None:
                    line.name = limpiar_texto_xml(fila[idx]) if fila[idx] is not None else ""

            if estilo and isinstance(estilo, dict):
                color = estilo.get("color")
                width = estilo.get("width", 2.0)
                if color:
                    line.style.linestyle.color = kml_color(color)
                line.style.linestyle.width = width

            for i, campo in enumerate(cols):
                try:
                    line.extendeddata.newdata(campo, limpiar_texto_xml(fila[i]))
                except Exception:
                    pass

        except Exception as e:
            print(f"⚠ Error exportando línea {entidad} fila {fila}: {e}")
            traceback.print_exc()

# -----------------------------
# Exportar por trafo (UN SOLO KMZ con carpetas internas)
# -----------------------------
def exportar_kmz_por_trafo(salida, codigo_trafo, circuito=None, estilos=None, entidades_config=None, regional=None):
    """
    Genera un solo KMZ con carpetas internas (TRAFOS, POSTES_BT, RED_BT) para un trafo dado.
    Parámetros:
      - salida: ruta completa del .kmz de salida (archivo)
      - codigo_trafo: NODO_TRANSFORM_V que quieres exportar
      - circuito: (opcional) filtro circuito para las consultas
      - estilos: dict con claves "TRAFOS", "POSTES_BT_BY_TRAFO", "RED_BT_BY_TRAFO" (puede venir desde main)
      - entidades_config: dict con metadatos (opcional, para etiqueta/icon_href)
      - regional: (opcional) filtro región
    Retorna ruta del KMZ si ok, o None en error.
    """
    import simplekml, os
    estilos = estilos or {}
    entidades_config = entidades_config or {}

    def normalize_color_to_hex(color):
        # acepta '#RRGGBB', 'RRGGBB' o 'AABBGGRR' (devuelve '#RRGGBB')
        if not color:
            return "#FF0000"
        s = str(color).strip()
        if s.startswith("#"):
            s = s[1:]
        if len(s) == 8:  # AABBGGRR -> RRGGBB
            return "#" + s[6:8] + s[4:6] + s[2:4]
        if len(s) == 6:
            return "#" + s
        return "#FF0000"

    def safe_float(v):
        try:
            return float(v)
        except Exception:
            return None

    try:
        # asegurar carpeta destino
        out_dir = os.path.dirname(salida)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        kml = simplekml.Kml()

        # ====== TRAFOS ======
        trafos, cols_t = ejecutar_consulta(queries["TRAFOS"], {"regional": regional, "circuito": circuito})
        print("Columnas TRAFOS:", cols_t)
        print("Primeros 5 TRAFOS:", trafos[:5])

        folder_trafo = kml.newfolder(name="TRAFOS")

        estilo_trafo = estilos.get("TRAFOS", {}) or entidades_config.get("TRAFOS", {}).get("estilo", {})
        icon_trafo = estilo_trafo.get("icon_href")
        scale_trafo = estilo_trafo.get("scale", 1.2)
        color_trafo_hex = normalize_color_to_hex(estilo_trafo.get("color"))

        # localizar índices de lon/lat para trafos
        def _point_indices(cols):
            if not cols:
                return -2, -1
            if "COOR_GPS_LON" in cols and "COOR_GPS_LAT" in cols:
                return cols.index("COOR_GPS_LON"), cols.index("COOR_GPS_LAT")
            if "COOR_X" in cols and "COOR_Y" in cols:
                return cols.index("COOR_X"), cols.index("COOR_Y")
            # fallback: últimas dos columnas
            return len(cols)-2, len(cols)-1

        lon_idx_t, lat_idx_t = _point_indices(cols_t)

        for row in trafos:
            try:
                # compara por NODO_TRANSFORM_V
                if "NODO_TRANSFORM_V" in cols_t and str(row[cols_t.index("NODO_TRANSFORM_V")]) == str(codigo_trafo):
                    lon = safe_float(row[lon_idx_t]) if lon_idx_t < len(row) else None
                    lat = safe_float(row[lat_idx_t]) if lat_idx_t < len(row) else None
                    if lon is None or lat is None:
                        print("⚠ Trafo sin coords, saltando:", row)
                        continue
                    p = folder_trafo.newpoint(coords=[(lon, lat)])
                    # etiqueta: si hay etiqueta en entidades_config
                    etiqueta = entidades_config.get("TRAFOS", {}).get("etiqueta")
                    if etiqueta and etiqueta in cols_t:
                        p.name = limpiar_texto_xml(row[cols_t.index(etiqueta)])
                    else:
                        # si no, ponemos el NODO_TRANSFORM_V
                        p.name = limpiar_texto_xml(str(row[cols_t.index("NODO_TRANSFORM_V")]) if "NODO_TRANSFORM_V" in cols_t else codigo_trafo)

                    # icono o color/size
                    if icon_trafo and os.path.exists(icon_trafo):
                        p.style.iconstyle.icon.href = icon_trafo
                        p.style.iconstyle.scale = scale_trafo
                    else:
                        # aplicar color de fallback si no hay icon
                        p.style.iconstyle.color = kml_color(color_trafo_hex)
                        p.style.iconstyle.scale = scale_trafo

                    # atributos
                    for i, col in enumerate(cols_t):
                        try:
                            p.extendeddata.newdata(col, limpiar_texto_xml(row[i]))
                        except Exception:
                            pass
            except Exception as e:
                print("⚠ Error procesando trafo fila:", e)

        # ====== POSTES BT ======
        postes, cols_p = ejecutar_consulta(queries["POSTES_BT_BY_TRAFO"], {"codigo_trafo": codigo_trafo, "regional": regional})
        print("Columnas POSTES:", cols_p)
        print("Primeros 5 POSTES:", postes[:5])

        folder_postes = kml.newfolder(name="POSTES_BT")

        estilo_postes = estilos.get("POSTES_BT_BY_TRAFO", {}) or entidades_config.get("POSTES_BT_BY_TRAFO", {}).get("estilo", {})
        icon_poste = estilo_postes.get("icon_href")
        scale_poste = estilo_postes.get("scale", 0.9)
        color_poste_hex = normalize_color_to_hex(estilo_postes.get("color"))

        lon_idx_p, lat_idx_p = _point_indices(cols_p)

        for row in postes:
            try:
                lon = safe_float(row[lon_idx_p]) if lon_idx_p < len(row) else None
                lat = safe_float(row[lat_idx_p]) if lat_idx_p < len(row) else None
                if lon is None or lat is None:
                    print("⚠ Poste sin coords, saltando:", row)
                    continue
                p = folder_postes.newpoint(coords=[(lon, lat)])
                etiqueta = entidades_config.get("POSTES_BT_BY_TRAFO", {}).get("etiqueta")
                if etiqueta and etiqueta in cols_p:
                    p.name = limpiar_texto_xml(row[cols_p.index(etiqueta)])
                else:
                    # usar CODIGO si existe
                    if "CODIGO" in cols_p:
                        p.name = limpiar_texto_xml(str(row[cols_p.index("CODIGO")]))
                    else:
                        p.name = ""

                if icon_poste and os.path.exists(icon_poste):
                    p.style.iconstyle.icon.href = icon_poste
                    p.style.iconstyle.scale = scale_poste
                else:
                    p.style.iconstyle.color = kml_color(color_poste_hex)
                    p.style.iconstyle.scale = scale_poste

                for i, col in enumerate(cols_p):
                    try:
                        p.extendeddata.newdata(col, limpiar_texto_xml(row[i]))
                    except Exception:
                        pass
            except Exception as e:
                print("⚠ Error procesando poste fila:", e)

        # ====== RED BT (líneas) ======
        redes, cols_r = ejecutar_consulta(queries["RED_BT_BY_TRAFO"], {"codigo_trafo": codigo_trafo, "regional": regional})
        print("Columnas RED_BT:", cols_r)
        print("Primeros 5 RED_BT:", redes[:5])

        folder_red = kml.newfolder(name="RED_BT")

        estilo_red = estilos.get("RED_BT_BY_TRAFO", {}) or entidades_config.get("RED_BT_BY_TRAFO", {}).get("estilo", {})
        color_red_hex = normalize_color_to_hex(estilo_red.get("color"))
        width_red = float(estilo_red.get("width", 2.5) or 2.5)

        for row in redes:
            try:
                lon1, lat1, lon2, lat2 = obtener_coords_linea(cols_r, row)
                if None in (lon1, lat1, lon2, lat2):
                    print("⚠ Línea sin coords completas, saltando:", row)
                    continue
                line = folder_red.newlinestring(coords=[(lon1, lat1, 0), (lon2, lat2, 0)])
                line.altitudemode = simplekml.AltitudeMode.clamptoground
                line.tessellate = 1
                line.style.linestyle.color = kml_color(color_red_hex)
                line.style.linestyle.width = max(width_red, 1.0)
                etiqueta = entidades_config.get("RED_BT_BY_TRAFO", {}).get("etiqueta")
                if etiqueta and etiqueta in cols_r:
                    line.name = limpiar_texto_xml(row[cols_r.index(etiqueta)])
                else:
                    if "CODIGO" in cols_r:
                        line.name = limpiar_texto_xml(str(row[cols_r.index("CODIGO")]))
                    else:
                        line.name = ""
                for i, col in enumerate(cols_r):
                    try:
                        line.extendeddata.newdata(col, limpiar_texto_xml(row[i]))
                    except Exception:
                        pass
            except Exception as e:
                print("⚠ Error procesando línea fila:", e)

        # Guardar KMZ
        kml.savekmz(salida)
        print(f"✅ KMZ generado: {salida}")
        return salida

    except Exception as e:
        print("❌ Error en exportar_kmz_por_trafo:", e)
        traceback.print_exc()
        return None

# ==============================
# Consultas auxiliares (circuitos / trafos)
# ==============================
def obtener_circuitos(regional=None):
    try:
        conn = conectar_oracle()
        cur = conn.cursor()
        if regional:
            query = """
                SELECT DISTINCT TRIM(N.CIRCUITO)
                FROM CCOMUN@GTECH B
                JOIN EPOSTE_AT@GTECH C ON B.G3E_FID = C.G3E_FID
                JOIN NORMA@GTECH N ON C.G3E_FID = N.G3E_FID
                JOIN CELE_NOR_GRP_CAT@GTECH E ON E.NORMA = N.NORMA
                JOIN EINTERRU_AT@GTECH I ON I.CODIGO = N.CIRCUITO
                JOIN CCONECTIVIDAD_E@GTECH Z ON I.G3E_FID = Z.G3E_FID
                WHERE B.G3E_FNO = 17100
                  AND B.ESTADO = 'OPERACION'
                  AND C.TIPO LIKE '%PRIMARIO%'
                  AND E.TIPO_RED = 'PRIMARIA'
                  AND N.NORMA NOT IN ('SPT','712','710','711','730','731')
                  AND C.TIPO_INSTALACION IS NULL
                  AND N.CIRCUITO IS NOT NULL
                  AND LENGTH(TRIM(N.CIRCUITO)) > 3
                  AND REGEXP_LIKE(N.CIRCUITO, '^[A-Z0-9_]+$')
                  AND UPPER(B.REGION) = :regional
            """
            cur.execute(query, {"regional": regional})
        else:
            cur.execute("""
                SELECT DISTINCT TRIM(N.CIRCUITO)
                FROM CCOMUN@GTECH B
                JOIN EPOSTE_AT@GTECH C ON B.G3E_FID = C.G3E_FID
                JOIN NORMA@GTECH N ON C.G3E_FID = N.G3E_FID
                JOIN CELE_NOR_GRP_CAT@GTECH E ON E.NORMA = N.NORMA
                JOIN EINTERRU_AT@GTECH I ON I.CODIGO = N.CIRCUITO
                JOIN CCONECTIVIDAD_E@GTECH Z ON I.G3E_FID = Z.G3E_FID
                WHERE B.G3E_FNO = 17100
                  AND B.ESTADO = 'OPERACION'
                  AND C.TIPO LIKE '%PRIMARIO%'
                  AND E.TIPO_RED = 'PRIMARIA'
                  AND N.NORMA NOT IN ('SPT','712','710','711','730','731')
                  AND C.TIPO_INSTALACION IS NULL
                  AND N.CIRCUITO IS NOT NULL
                  AND LENGTH(TRIM(N.CIRCUITO)) > 3
                  AND REGEXP_LIKE(N.CIRCUITO, '^[A-Z0-9_]+$')
            """)
        circuitos = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return sorted(set(circuitos))
    except Exception as e:
        print(f"❌ Error consultando circuitos: {e}")
        traceback.print_exc()
        return []

def obtener_trafos(circuito=None, regional=None):
    try:
        conn = conectar_oracle()
        cur = conn.cursor()

        sql = """
            SELECT DISTINCT CE.NODO_TRANSFORM_V
            FROM CCOMUN@GTECH C
            JOIN ETRANSFO_AT@GTECH T ON C.G3E_FID = T.G3E_FID
            JOIN CCONECTIVIDAD_E@GTECH CE ON CE.G3E_FID = C.G3E_FID AND CE.G3E_FNO = 20400
            WHERE C.ESTADO = 'OPERACION'
        """
        params = {}
        if circuito:
            sql += " AND CE.CIRCUITO = :circuito"
            params["circuito"] = circuito
        if regional:
            sql += " AND UPPER(C.REGION) = :regional"
            params["regional"] = regional.upper()
        sql += " ORDER BY CE.NODO_TRANSFORM_V"

        cur.execute(sql, params)
        trafos = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return sorted(set(trafos))
    except Exception as e:
        print(f"❌ Error consultando trafos para circuito {circuito}: {e}")
        traceback.print_exc()
        return []

def obtener_trafos_por_circuito(circuito, regional=None):
    """
    Retorna (datos, columnas) con NODO_TRANSFORM_V asociados al circuito/región.
    """
    try:
        sql = """
            SELECT DISTINCT CE.NODO_TRANSFORM_V
            FROM CCOMUN@GTECH C
            JOIN ETRANSFO_AT@GTECH T ON C.G3E_FID = T.G3E_FID
            JOIN CCONECTIVIDAD_E@GTECH CE ON CE.G3E_FID = C.G3E_FID AND CE.G3E_FNO = 20400
            WHERE C.ESTADO = 'OPERACION'
              AND CE.CIRCUITO = :circuito
        """
        params = {"circuito": circuito}
        if regional:
            sql += " AND UPPER(C.REGION) = :regional"
            params["regional"] = regional.upper()
        sql += " ORDER BY CE.NODO_TRANSFORM_V"
        datos, cols = ejecutar_consulta(sql, params)
        return datos, cols
    except Exception as e:
        print("Error en obtener_trafos_por_circuito:", e)
        traceback.print_exc()
        return [], []

# fin de core.py
