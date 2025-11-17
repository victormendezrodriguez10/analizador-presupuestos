import streamlit as st
import psycopg2
import pandas as pd
import json
import requests
import xml.etree.ElementTree as ET
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

st.set_page_config(page_title="Análisis de Bajas Estadísticas", page_icon="📊", layout="wide")

# Conexión a base de datos
def get_connection():
    """Crear nueva conexión a la base de datos"""
    try:
        conn = psycopg2.connect(
            host=st.secrets["postgres"]["host"],
            database=st.secrets["postgres"]["database"],
            user=st.secrets["postgres"]["user"],
            password=st.secrets["postgres"]["password"],
            port=st.secrets["postgres"]["port"]
        )
        return conn
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return None

def get_tag_name(element):
    """Obtener nombre del tag sin namespace"""
    return element.tag.split('}')[-1] if '}' in element.tag else element.tag

def extraer_datos_xml_completo(url):
    """Extraer datos completos del XML incluyendo lotes - VERSIÓN MEJORADA"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        # Datos generales
        datos = {
            'titulo': '',
            'organismo': '',
            'ubicacion': '',
            'lotes': []
        }

        st.info("🔍 **DEBUG: Estructura del XML**")

        # BUSCAR TÍTULO - Versión mejorada
        st.write("**Buscando título...**")
        for elem in root.iter():
            tag = get_tag_name(elem)

            # Buscar en ProcurementProject > Name
            if tag == 'ProcurementProject':
                for child in elem:
                    child_tag = get_tag_name(child)
                    if child_tag == 'Name' and child.text:
                        texto = child.text.strip()
                        if len(texto) > 15:
                            datos['titulo'] = texto
                            st.success(f"✅ Título encontrado en ProcurementProject/Name: `{texto}`")
                            break
                if datos['titulo']:
                    break

        # Si no encontró, buscar en cualquier Name largo
        if not datos['titulo']:
            for elem in root.iter():
                tag = get_tag_name(elem)
                if tag == 'Name' and elem.text:
                    texto = elem.text.strip()
                    if len(texto) > 20 and 'http' not in texto.lower():
                        datos['titulo'] = texto
                        st.success(f"✅ Título encontrado en Name genérico: `{texto}`")
                        break

        if not datos['titulo']:
            st.warning("⚠️ No se pudo extraer el título")

        # BUSCAR ORGANISMO
        st.write("**Buscando organismo...****")
        for elem in root.iter():
            tag = get_tag_name(elem)
            if tag == 'PartyName' and elem.text:
                datos['organismo'] = elem.text.strip()
                st.success(f"✅ Organismo encontrado: `{datos['organismo']}`")
                break

        # BUSCAR UBICACIÓN
        for elem in root.iter():
            tag = get_tag_name(elem)
            if tag == 'CityName' and elem.text:
                datos['ubicacion'] = elem.text.strip()
                st.success(f"✅ Ubicación: `{datos['ubicacion']}`")
                break

        # BUSCAR LOTES
        st.write("**Buscando lotes...**")
        lotes_encontrados = 0

        for elem in root.iter():
            tag = get_tag_name(elem)
            if tag == 'ProcurementProjectLot':
                lote = {
                    'numero': '',
                    'titulo': '',
                    'presupuesto': 0,
                    'cpv': [],
                    'criterios': []
                }

                # ID del lote
                for child in elem.iter():
                    child_tag = get_tag_name(child)
                    if child_tag == 'ID' and child.text:
                        lote['numero'] = child.text.strip()
                        break

                # Título del lote
                for child in elem.iter():
                    child_tag = get_tag_name(child)
                    if child_tag == 'Name' and child.text:
                        if len(child.text.strip()) > 10:
                            lote['titulo'] = child.text.strip()
                            break

                # Presupuesto
                for child in elem.iter():
                    child_tag = get_tag_name(child)
                    if 'Amount' in child_tag and child.text:
                        try:
                            lote['presupuesto'] = float(child.text.strip())
                            break
                        except:
                            pass

                # CPVs
                for child in elem.iter():
                    child_tag = get_tag_name(child)
                    if child_tag == 'ItemClassificationCode' and child.text:
                        cpv_digits = ''.join(filter(str.isdigit, child.text))
                        if len(cpv_digits) >= 4:
                            lote['cpv'].append(cpv_digits)

                # Criterios
                for child in elem.iter():
                    child_tag = get_tag_name(child)
                    if 'Criteria' in child_tag or 'Criterion' in child_tag:
                        criterio = {}
                        for subchild in child:
                            subtag = get_tag_name(subchild)
                            if subchild.text:
                                if any(x in subtag for x in ['Description', 'Name']):
                                    criterio['descripcion'] = subchild.text.strip()
                                elif any(x in subtag for x in ['Weight', 'Numeric']):
                                    criterio['peso'] = subchild.text.strip()

                        if criterio.get('descripcion'):
                            lote['criterios'].append(criterio)

                if lote['presupuesto'] > 0 or lote['cpv']:
                    if not lote['numero']:
                        lote['numero'] = str(len(datos['lotes']) + 1)
                    datos['lotes'].append(lote)
                    lotes_encontrados += 1
                    st.success(f"✅ Lote {lote['numero']}: {lote['titulo'][:50]}, Presupuesto: €{lote['presupuesto']:,.2f}, CPVs: {', '.join(lote['cpv'])}")

        # Si no hay lotes, buscar datos a nivel general
        if not datos['lotes']:
            st.write("**No se encontraron lotes, buscando datos generales...**")
            lote_general = {
                'numero': '1',
                'titulo': datos['titulo'] or 'Contrato único',
                'presupuesto': 0,
                'cpv': [],
                'criterios': []
            }

            # Buscar presupuesto general
            for elem in root.iter():
                tag = get_tag_name(elem)
                if 'Amount' in tag and elem.text:
                    try:
                        valor = float(elem.text.strip())
                        if valor > lote_general['presupuesto']:
                            lote_general['presupuesto'] = valor
                    except:
                        pass

            st.write(f"💰 Presupuesto encontrado: €{lote_general['presupuesto']:,.2f}")

            # Buscar CPVs generales
            for elem in root.iter():
                tag = get_tag_name(elem)
                if tag == 'ItemClassificationCode':
                    cpv_text = elem.get('listID') or elem.text
                    if cpv_text:
                        cpv_digits = ''.join(filter(str.isdigit, cpv_text))
                        if len(cpv_digits) >= 4 and cpv_digits not in lote_general['cpv']:
                            lote_general['cpv'].append(cpv_digits)

            st.write(f"📋 CPVs encontrados: {', '.join(lote_general['cpv'])}")

            # Buscar criterios generales
            criterios_count = 0
            for elem in root.iter():
                tag = get_tag_name(elem)
                if 'Criteria' in tag or 'Criterion' in tag:
                    criterio = {}
                    for child in elem:
                        child_tag = get_tag_name(child)
                        if child.text:
                            if any(x in child_tag for x in ['Description', 'Name']):
                                criterio['descripcion'] = child.text.strip()
                            elif any(x in child_tag for x in ['Weight', 'Numeric', 'Percent']):
                                criterio['peso'] = child.text.strip()

                    if criterio.get('descripcion') and criterio not in lote_general['criterios']:
                        lote_general['criterios'].append(criterio)
                        criterios_count += 1

            st.write(f"⚖️ Criterios encontrados: {criterios_count}")
            for i, c in enumerate(lote_general['criterios'], 1):
                st.write(f"  {i}. {c.get('descripcion', 'Sin descripción')}: {c.get('peso', 'Sin peso')}")

            if lote_general['presupuesto'] > 0 or lote_general['cpv']:
                datos['lotes'].append(lote_general)
                st.success("✅ Datos generales extraídos correctamente")
            else:
                st.error("❌ No se pudo extraer información útil del XML")

        return datos
    except Exception as e:
        st.error(f"Error al procesar XML: {e}")
        import traceback
        st.code(traceback.format_exc())
        return None

# Resto del código igual que analisis_mejorado.py...
# (Copiando las funciones de búsqueda y generación de informes)

def extraer_palabras_clave_inteligentes(texto):
    """Extraer solo las palabras clave MÁS relevantes del título"""
    import re

    # Normalizar texto
    def normalizar(texto):
        texto = texto.lower()
        texto = re.sub(r'[áàäâ]', 'a', texto)
        texto = re.sub(r'[éèëê]', 'e', texto)
        texto = re.sub(r'[íìïî]', 'i', texto)
        texto = re.sub(r'[óòöô]', 'o', texto)
        texto = re.sub(r'[úùüû]', 'u', texto)
        return texto

    texto_norm = normalizar(texto)
    texto_norm = re.sub(r'[^a-z0-9\s]', ' ', texto_norm)
    palabras = texto_norm.split()

    # Palabras a ignorar completamente
    palabras_ignorar = {
        'de', 'del', 'la', 'el', 'los', 'las', 'y', 'a', 'en', 'para', 'con', 'por', 'segun',
        'contrato', 'servicio', 'servicios', 'suministro', 'obra', 'obras', 'lote',
        'mediante', 'procedimiento', 'abierto', 'simplificado', 'menor', 'expediente',
        'una', 'uno', 'unos', 'unas', 'este', 'esta', 'estos', 'estas', 'ese', 'esa',
        'municipal', 'municipales', 'apartado', 'cuadro', 'resumen', 'pcap', 'ppt',
        'ayuntamiento', 'diputacion'
    }

    # Términos técnicos específicos que SÍ queremos capturar
    terminos_tecnicos = {
        'redes', 'sociales', 'marketing', 'digital', 'community', 'manager', 'publicidad',
        'fotovoltaica', 'fotovoltaico', 'solar', 'climatizacion', 'calefaccion'
    }

    palabras_clave = set()

    # 1. Buscar términos técnicos individuales
    for palabra in palabras:
        if palabra in terminos_tecnicos:
            palabras_clave.add(palabra)

    # 2. Si no encontramos nada técnico, buscar sustantivos principales (palabras largas)
    if not palabras_clave:
        for palabra in palabras:
            if (len(palabra) > 6 and
                palabra not in palabras_ignorar and
                not palabra.isdigit()):
                palabras_clave.add(palabra)

    # 3. Limitar a máximo 5 palabras clave
    if len(palabras_clave) > 5:
        palabras_clave = set(sorted(palabras_clave, key=len, reverse=True)[:5])

    return palabras_clave

def calcular_similitud(titulo_base, titulo_comparar):
    """Calcular similitud entre dos títulos usando palabras clave inteligentes"""

    palabras_base = extraer_palabras_clave_inteligentes(titulo_base)
    palabras_comparar = extraer_palabras_clave_inteligentes(titulo_comparar)

    if not palabras_base or not palabras_comparar:
        return 0

    coincidencias = len(palabras_base.intersection(palabras_comparar))
    total = len(palabras_base) + len(palabras_comparar)

    if total == 0:
        return 0

    similitud = (coincidencias * 2) / total
    return min(similitud, 1.0)

def buscar_contratos(cpvs, presupuesto_min, presupuesto_max, titulo_referencia="", limit=10):
    """Buscar contratos similares por CPV y filtrar por relevancia"""
    if isinstance(cpvs, str):
        cpvs = [cpvs]

    # Estrategia escalonada: intentar con 4, 3, 2 dígitos
    cpv_patterns = []
    cpv_original = []

    for cpv in cpvs[:3]:
        cpv_digits = ''.join(filter(str.isdigit, str(cpv)))
        if len(cpv_digits) >= 4:
            cpv_patterns.append(cpv_digits[:4])  # 4 dígitos (específico)
            cpv_original.append(cpv_digits)
        elif len(cpv_digits) >= 2:
            cpv_patterns.append(cpv_digits[:2])  # 2 dígitos (genérico)

    if not cpv_patterns:
        st.warning("❌ No se pudieron extraer CPVs válidos")
        return []

    st.info(f"🔍 Buscando con CPVs: {', '.join(cpv_patterns)} (original: {', '.join(cpv_original)})")

    # Intentar primero con CPV específico (4 dígitos), luego más genérico
    cpv_condition = " OR ".join([f"cpv::text ~ '^{cpv}'" for cpv in cpv_patterns])

    limit_busqueda = 300  # Aumentado para tener más opciones

    # Ampliar MUCHO el rango de presupuesto
    presupuesto_min_amplio = presupuesto_min * 0.2  # 20% del mínimo
    presupuesto_max_amplio = presupuesto_max * 3.0  # 300% del máximo

    st.info(f"💰 Rango presupuesto: €{presupuesto_min_amplio:,.0f} - €{presupuesto_max_amplio:,.0f}")

    query = f"""
    SELECT
        titulo,
        entidad_compradora as organismo,
        importe_total,
        importe_adjudicacion,
        adjudicatario,
        numero_licitadores,
        fecha_publicacion,
        ROUND(((importe_total - importe_adjudicacion) / NULLIF(importe_total, 0) * 100)::numeric, 2) as baja,
        cpv,
        provincia
    FROM adjudicaciones_metabase
    WHERE importe_total IS NOT NULL
    AND importe_adjudicacion IS NOT NULL
    AND importe_total > 0
    AND importe_adjudicacion > 0
    AND importe_total != importe_adjudicacion
    AND ({cpv_condition})
    AND importe_total BETWEEN {presupuesto_min_amplio} AND {presupuesto_max_amplio}
    ORDER BY fecha_publicacion DESC
    LIMIT {limit_busqueda}
    """

    conn = None
    try:
        conn = get_connection()
        if not conn:
            return []

        cur = conn.cursor()
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        results = []

        for row in cur.fetchall():
            contrato = dict(zip(columns, row))

            # Extraer nombre de empresa
            adj_raw = contrato['adjudicatario']
            empresa = 'N/A'
            if adj_raw:
                try:
                    adj_str = str(adj_raw)
                    if adj_str.startswith('['):
                        adj_array = json.loads(adj_str)
                        if adj_array and 'adjudicatario' in adj_array[0]:
                            empresa = adj_array[0]['adjudicatario'].get('name', 'N/A')
                    elif adj_str.startswith('{'):
                        adj_dict = json.loads(adj_str)
                        if 'adjudicatario' in adj_dict:
                            empresa = adj_dict['adjudicatario'].get('name', 'N/A')
                    else:
                        empresa = adj_str[:80]
                except:
                    empresa = str(adj_raw)[:80] if adj_raw else 'N/A'

            contrato['empresa'] = empresa

            # Calcular similitud si hay título de referencia
            if titulo_referencia:
                similitud = calcular_similitud(titulo_referencia, contrato['titulo'])
                contrato['similitud'] = similitud
            else:
                contrato['similitud'] = 1.0

            results.append(contrato)

        cur.close()

        st.info(f"💾 Contratos recuperados de BD: {len(results)}")

        if not results:
            st.warning("❌ No se encontraron contratos con ese CPV y rango de presupuesto")
            return []

        # NUEVA LÓGICA: Priorizar recientes + similitud
        if titulo_referencia:
            palabras_objetivo = extraer_palabras_clave_inteligentes(titulo_referencia)
            st.info(f"🎯 Palabras clave del objetivo: {', '.join(sorted(palabras_objetivo))}")

            # Calcular un score combinado: 70% similitud + 30% recencia
            from datetime import datetime

            # Obtener fecha más antigua y más reciente
            fechas = [c['fecha_publicacion'] for c in results if c['fecha_publicacion']]
            if fechas:
                fecha_min = min(fechas)
                fecha_max = max(fechas)
                rango_fechas = (fecha_max - fecha_min).days if fecha_max != fecha_min else 1
            else:
                rango_fechas = 1

            # Calcular score combinado
            for c in results:
                similitud_score = c['similitud']

                # Score de recencia (contratos más recientes = score más alto)
                if c['fecha_publicacion'] and rango_fechas > 0:
                    dias_desde_antiguo = (c['fecha_publicacion'] - fecha_min).days
                    recencia_score = dias_desde_antiguo / rango_fechas
                else:
                    recencia_score = 0.5

                # Score combinado: 60% similitud + 40% recencia
                c['score_final'] = (similitud_score * 0.6) + (recencia_score * 0.4)

            # Ordenar por score final (más alto = mejor)
            results.sort(key=lambda x: x['score_final'], reverse=True)

            st.write("**Top 10 contratos (ordenados por relevancia + recencia):**")
            for i, c in enumerate(results[:10], 1):
                fecha_str = str(c['fecha_publicacion'])[:10] if c['fecha_publicacion'] else 'N/A'
                st.write(f"{i}. [Similitud: {c['similitud']:.0%} | Score: {c['score_final']:.0%} | {fecha_str}] {c['titulo'][:60]}")

        else:
            # Sin título de referencia, solo ordenar por fecha
            st.info("⚠️ Sin título de referencia, mostrando los más recientes")

        # SIEMPRE devolver resultados (los mejores 'limit' según el score o fecha)
        st.success(f"✅ Mostrando los {min(limit, len(results))} contratos más relevantes")
        return results[:limit]
    except Exception as e:
        st.error(f"Error en búsqueda: {e}")
        import traceback
        st.code(traceback.format_exc())
        return []
    finally:
        if conn:
            conn.close()

# Interfaz principal
st.title("📊 Análisis de Bajas Estadísticas (DEBUG)")
st.markdown("**Versión con información de diagnóstico**")
st.markdown("---")

xml_url = st.text_input(
    "Introduce la URL del XML del contrato:",
    placeholder="https://contrataciondelestado.es/FileSystem/servlet/...",
    help="Pega la URL completa del XML"
)

if st.button("🚀 Analizar Contrato", type="primary"):
    if not xml_url:
        st.warning("Por favor, introduce una URL")
    else:
        with st.spinner("Procesando XML..."):
            datos = extraer_datos_xml_completo(xml_url)

        if not datos or not datos['lotes']:
            st.error("No se pudieron extraer lotes del XML")
        else:
            st.success(f"✅ XML procesado - {len(datos['lotes'])} lote(s) encontrado(s)")

            # Analizar cada lote
            for lote in datos['lotes']:
                st.markdown("---")
                st.markdown(f"## 📦 Lote {lote['numero']}: {lote['titulo'][:80]}")

                st.markdown(f"**Presupuesto:** €{lote['presupuesto']:,.2f}")
                st.markdown(f"**CPV:** {', '.join(lote['cpv']) if lote['cpv'] else 'No especificado'}")

                # Criterios
                st.markdown("### ⚖️ Criterios de Adjudicación")
                if lote['criterios']:
                    for i, crit in enumerate(lote['criterios'], 1):
                        desc = crit.get('descripcion', f'Criterio {i}')
                        peso = crit.get('peso', '')
                        st.write(f"**{i}.** {desc}: **{peso}**" if peso else f"**{i}.** {desc}")
                else:
                    st.info("ℹ️ No se encontraron criterios de adjudicación en el XML")

                # Buscar contratos
                if lote['cpv'] and lote['presupuesto'] > 0:
                    st.markdown("### 🔍 Análisis de Mercado")

                    pres_min = lote['presupuesto'] * 0.5
                    pres_max = lote['presupuesto'] * 1.5

                    with st.spinner("Buscando contratos similares..."):
                        contratos = buscar_contratos(lote['cpv'], pres_min, pres_max, titulo_referencia=lote['titulo'], limit=10)

                    if not contratos:
                        st.warning(f"⚠️ No se encontraron contratos similares")
                    else:
                        st.success(f"✅ {len(contratos)} contratos encontrados")
                else:
                    st.warning("⚠️ No se pudo extraer CPV o presupuesto del lote")

st.markdown("---")
st.caption("📊 Versión DEBUG para diagnóstico")
