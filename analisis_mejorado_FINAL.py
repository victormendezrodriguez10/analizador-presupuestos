import streamlit as st
import psycopg2
import pandas as pd
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import random
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
    """Extraer datos completos del XML incluyendo lotes"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        datos = {
            'titulo': '',
            'organismo': '',
            'ubicacion': '',
            'lotes': []
        }

        # BUSCAR TÍTULO
        for elem in root.iter():
            tag = get_tag_name(elem)
            if tag == 'ProcurementProject':
                for child in elem:
                    child_tag = get_tag_name(child)
                    if child_tag == 'Name' and child.text:
                        texto = child.text.strip()
                        if len(texto) > 15:
                            datos['titulo'] = texto
                            break
                if datos['titulo']:
                    break

        if not datos['titulo']:
            for elem in root.iter():
                tag = get_tag_name(elem)
                if tag == 'Name' and elem.text:
                    texto = elem.text.strip()
                    if len(texto) > 20 and 'http' not in texto.lower():
                        datos['titulo'] = texto
                        break

        # BUSCAR ORGANISMO
        for elem in root.iter():
            tag = get_tag_name(elem)
            if tag == 'PartyName' and elem.text:
                datos['organismo'] = elem.text.strip()
                break

        # BUSCAR UBICACIÓN (Ciudad y Provincia)
        for elem in root.iter():
            tag = get_tag_name(elem)
            if tag == 'CityName' and elem.text:
                datos['ubicacion'] = elem.text.strip()
            if tag == 'CountrySubentityCode' and elem.text:
                # Código de provincia (ej: ES-M para Madrid)
                datos['provincia_codigo'] = elem.text.strip()
            if tag == 'CountrySubentity' and elem.text:
                # Nombre de la provincia
                datos['provincia'] = elem.text.strip()

        # BUSCAR LOTES
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

                for child in elem.iter():
                    child_tag = get_tag_name(child)
                    if child_tag == 'ID' and child.text:
                        lote['numero'] = child.text.strip()
                        break

                for child in elem.iter():
                    child_tag = get_tag_name(child)
                    if child_tag == 'Name' and child.text:
                        if len(child.text.strip()) > 10:
                            lote['titulo'] = child.text.strip()
                            break

                for child in elem.iter():
                    child_tag = get_tag_name(child)
                    if 'Amount' in child_tag and child.text:
                        try:
                            lote['presupuesto'] = float(child.text.strip())
                            break
                        except:
                            pass

                for child in elem.iter():
                    child_tag = get_tag_name(child)
                    if child_tag == 'ItemClassificationCode' and child.text:
                        cpv_digits = ''.join(filter(str.isdigit, child.text))
                        if len(cpv_digits) >= 4:
                            lote['cpv'].append(cpv_digits)

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

        # Si no hay lotes, buscar datos generales
        if not datos['lotes']:
            lote_general = {
                'numero': '1',
                'titulo': datos['titulo'] or 'Contrato único',
                'presupuesto': 0,
                'cpv': [],
                'criterios': []
            }

            for elem in root.iter():
                tag = get_tag_name(elem)
                if 'Amount' in tag and elem.text:
                    try:
                        valor = float(elem.text.strip())
                        if valor > lote_general['presupuesto']:
                            lote_general['presupuesto'] = valor
                    except:
                        pass

            for elem in root.iter():
                tag = get_tag_name(elem)
                if tag == 'ItemClassificationCode':
                    cpv_text = elem.get('listID') or elem.text
                    if cpv_text:
                        cpv_digits = ''.join(filter(str.isdigit, cpv_text))
                        if len(cpv_digits) >= 4 and cpv_digits not in lote_general['cpv']:
                            lote_general['cpv'].append(cpv_digits)

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

            if lote_general['presupuesto'] > 0 or lote_general['cpv']:
                datos['lotes'].append(lote_general)

        return datos
    except Exception as e:
        st.error(f"Error al procesar XML: {e}")
        return None

def _extract_multilang_value(value):
    """Extraer texto de objetos multiidioma (ca, es, en, oc)"""
    if isinstance(value, dict):
        # Priorizar catalán, luego español, inglés y occitano
        for lang in ['ca', 'es', 'en', 'oc']:
            if lang in value and value[lang]:
                return value[lang]
        # Si no hay idiomas, intentar con 'name' o el primer valor string
        if 'name' in value:
            return value['name']
        if 'nom' in value:
            return value['nom']
        # Devolver el primer valor string que encuentre
        for v in value.values():
            if isinstance(v, str) and v.strip():
                return v
    return value

def _find_json_value(data, key_to_find):
    """Buscar una clave en un JSON de manera recursiva (case-insensitive)"""
    if isinstance(data, dict):
        # Buscar directamente (case-insensitive)
        for key, value in data.items():
            if key.lower() == key_to_find.lower() and value:
                return value

        # Buscar recursivamente en valores anidados
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                result = _find_json_value(value, key_to_find)
                if result:
                    return result
    elif isinstance(data, list):
        for item in data:
            result = _find_json_value(item, key_to_find)
            if result:
                return result

    return None

def extraer_datos_json_completo(json_data):
    """Extraer datos completos del JSON incluyendo lotes"""
    try:
        # Si es un string, parsearlo como JSON
        if isinstance(json_data, str):
            data = json.loads(json_data)
        elif isinstance(json_data, dict):
            data = json_data
        else:
            st.error("Formato JSON no válido")
            return None

        datos = {
            'titulo': '',
            'organismo': '',
            'ubicacion': '',
            'lotes': []
        }

        # BUSCAR TÍTULO
        titulo_keys = ['titulo', 'title', 'name', 'objeto', 'description', 'asunto', 'denominacion', 'denominacio']
        for key in titulo_keys:
            value = _find_json_value(data, key)
            if value:
                titulo_text = _extract_multilang_value(value)
                if titulo_text:
                    datos['titulo'] = str(titulo_text).strip()
                    break

        # BUSCAR ORGANISMO
        organismo_keys = ['organismo', 'entidad', 'organo', 'organ', 'buyer', 'contracting_authority', 'contratante', 'administracion', 'nom']
        for key in organismo_keys:
            value = _find_json_value(data, key)
            if value:
                # Si el valor es un objeto (como 'organ'), buscar 'nom' o 'name' dentro
                if isinstance(value, dict) and ('nom' in value or 'name' in value):
                    datos['organismo'] = str(value.get('nom') or value.get('name')).strip()
                    break
                else:
                    organismo_text = _extract_multilang_value(value)
                    if organismo_text:
                        datos['organismo'] = str(organismo_text).strip()
                        break

        # BUSCAR UBICACIÓN
        ubicacion_keys = ['ubicacion', 'lugar', 'provincia', 'localitat', 'location', 'place', 'region', 'city', 'address', 'llocExecucio']
        for key in ubicacion_keys:
            value = _find_json_value(data, key)
            if value:
                ubicacion_text = _extract_multilang_value(value)
                if ubicacion_text:
                    datos['ubicacion'] = str(ubicacion_text).strip()
                    break

        # BUSCAR LOTES (o usar el documento completo como un único lote)
        lotes_data = _find_json_value(data, 'dadesPublicacioLot') or _find_json_value(data, 'lotes') or _find_json_value(data, 'lots')

        if lotes_data and isinstance(lotes_data, list):
            # Hay lotes definidos
            for idx, lote_data in enumerate(lotes_data, 1):
                lote = extraer_lote_json(lote_data, idx)
                if lote:
                    datos['lotes'].append(lote)
        else:
            # No hay lotes, usar el documento completo como un único lote
            lote = extraer_lote_json(data, 1)
            if lote:
                datos['lotes'].append(lote)

        return datos

    except Exception as e:
        st.error(f"Error al procesar JSON: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None

def extraer_lote_json(lote_data, numero_lote):
    """Extraer información de un lote desde JSON"""
    try:
        lote = {
            'numero': str(numero_lote),
            'titulo': '',
            'presupuesto': 0,
            'cpv': [],
            'criterios': []
        }

        # BUSCAR TÍTULO DEL LOTE
        titulo_keys = ['titulo', 'denominacion', 'denominacio', 'name', 'description']
        for key in titulo_keys:
            value = _find_json_value(lote_data, key)
            if value:
                titulo_text = _extract_multilang_value(value)
                if titulo_text and len(str(titulo_text).strip()) > 10:
                    lote['titulo'] = str(titulo_text).strip()
                    break

        # BUSCAR PRESUPUESTO
        presupuesto_keys = ['presupuesto', 'pressupost', 'pressupostLicitacio', 'pressupostBaseLicitacioAmbIva',
                          'precio', 'valor', 'importe', 'amount', 'budget', 'value', 'estimatedValue']
        for key in presupuesto_keys:
            value = _find_json_value(lote_data, key)
            if value:
                try:
                    if isinstance(value, (int, float)):
                        lote['presupuesto'] = float(value)
                        break
                    elif isinstance(value, str):
                        import re
                        clean_value = re.sub(r'[^\d.,]', '', value.replace(',', '.'))
                        if clean_value:
                            lote['presupuesto'] = float(clean_value)
                            break
                except:
                    continue

        # BUSCAR CPV
        cpv_keys = ['cpv', 'cpvPrincipal', 'codigo', 'codi', 'classification', 'classificationCode', 'cpv_code']
        for key in cpv_keys:
            value = _find_json_value(lote_data, key)
            if value:
                # Si es un objeto (como cpvPrincipal), buscar 'codi' o 'codigo'
                if isinstance(value, dict):
                    cpv_value = value.get('codi') or value.get('codigo') or value.get('code')
                    if cpv_value:
                        lote['cpv'].append(str(cpv_value).strip())
                        break
                # Si es una lista, tomar todos los códigos
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            cpv_value = item.get('codi') or item.get('codigo') or item.get('code')
                            if cpv_value:
                                lote['cpv'].append(str(cpv_value).strip())
                        elif isinstance(item, str) and item.strip():
                            lote['cpv'].append(item.strip())
                    if lote['cpv']:
                        break
                else:
                    # Si es string, añadirlo directamente
                    cpv_str = str(value).strip()
                    if cpv_str:
                        lote['cpv'].append(cpv_str)
                        break

        # BUSCAR CRITERIOS DE ADJUDICACIÓN
        criterios_keys = ['criterios', 'criterisAdjudicacio', 'criteria', 'awardingCriteria', 'evaluationCriteria']
        for key in criterios_keys:
            criterios_data = _find_json_value(lote_data, key)
            if criterios_data and isinstance(criterios_data, list):
                for criterio in criterios_data:
                    if isinstance(criterio, dict):
                        # Buscar descripción
                        desc_keys = ['descripcion', 'description', 'name', 'titulo', 'criteri']
                        desc_text = None
                        for desc_key in desc_keys:
                            if desc_key in criterio and criterio[desc_key]:
                                desc_value = _extract_multilang_value(criterio[desc_key])
                                if desc_value:
                                    desc_text = str(desc_value).strip()
                                    break

                        # Buscar peso
                        peso_keys = ['peso', 'weight', 'puntos', 'points', 'percentage', 'ponderacio']
                        peso_text = None
                        for peso_key in peso_keys:
                            if peso_key in criterio and criterio[peso_key]:
                                peso_val = criterio[peso_key]
                                if isinstance(peso_val, (int, float)):
                                    peso_text = f"{peso_val}%"
                                else:
                                    peso_text = str(peso_val)
                                break

                        # Si tiene desglossament (formato Diputació), procesarlo
                        if 'desglossament' in criterio and isinstance(criterio['desglossament'], list):
                            for subcriterio in criterio['desglossament']:
                                if isinstance(subcriterio, dict):
                                    sub_desc = None
                                    if 'descripcioCriteri' in subcriterio:
                                        sub_desc = _extract_multilang_value(subcriterio['descripcioCriteri'])
                                    elif 'tipusCriteri' in subcriterio:
                                        sub_desc = _extract_multilang_value(subcriterio['tipusCriteri'])

                                    sub_peso = None
                                    if 'puntuacio' in subcriterio:
                                        sub_peso = f"{subcriterio['puntuacio']}%"

                                    if sub_desc:
                                        lote['criterios'].append(f"{sub_desc}: {sub_peso}" if sub_peso else sub_desc)
                        else:
                            # Añadir criterio normal
                            if desc_text:
                                criterio_str = f"{desc_text}: {peso_text}" if peso_text else desc_text
                                lote['criterios'].append(criterio_str)
                break

        return lote if lote['presupuesto'] > 0 else None

    except Exception as e:
        st.warning(f"Error al procesar lote {numero_lote}: {e}")
        return None

def extraer_palabras_clave(texto):
    """Extraer palabras clave relevantes del título"""
    import re

    # Normalizar texto
    texto = texto.lower()
    texto = re.sub(r'[áàäâ]', 'a', texto)
    texto = re.sub(r'[éèëê]', 'e', texto)
    texto = re.sub(r'[íìïî]', 'i', texto)
    texto = re.sub(r'[óòöô]', 'o', texto)
    texto = re.sub(r'[úùüû]', 'u', texto)
    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)

    palabras = texto.split()

    # Palabras a ignorar
    ignorar = {
        'de', 'del', 'la', 'el', 'los', 'las', 'y', 'a', 'en', 'para', 'con', 'por',
        'contrato', 'servicio', 'servicios', 'suministro', 'obra', 'obras', 'lote',
        'mediante', 'procedimiento', 'abierto', 'simplificado', 'menor',
        'ayuntamiento', 'diputacion', 'municipal'
    }

    # Filtrar palabras relevantes (más de 4 letras y no en lista de ignorar)
    palabras_clave = [p for p in palabras if len(p) > 4 and p not in ignorar]

    return set(palabras_clave)

def calcular_similitud_palabras(titulo_base, titulo_comparar):
    """Calcular similitud basada en palabras clave comunes"""
    palabras_base = extraer_palabras_clave(titulo_base)
    palabras_comp = extraer_palabras_clave(titulo_comparar)

    if not palabras_base or not palabras_comp:
        return 0

    # Palabras en común
    comunes = palabras_base.intersection(palabras_comp)

    if not comunes:
        return 0

    # Similitud = palabras comunes / promedio de palabras totales
    similitud = len(comunes) / ((len(palabras_base) + len(palabras_comp)) / 2)

    return min(similitud, 1.0)

def detectar_grupo_similar(bajas, tolerancia=4):
    """
    Detecta el grupo más grande de bajas correlativas donde cada baja
    tiene una diferencia ≤ tolerancia (4%) con la siguiente.
    Retorna el grupo más grande de bajas correlativas (mínimo 2)
    """
    if len(bajas) < 2:
        return []

    # Ordenar bajas
    bajas_ordenadas = sorted(bajas)
    grupos = []

    # Buscar todos los grupos posibles
    i = 0
    while i < len(bajas_ordenadas):
        grupo_actual = [bajas_ordenadas[i]]

        # Agregar bajas consecutivas mientras la diferencia sea ≤ tolerancia
        j = i + 1
        while j < len(bajas_ordenadas):
            diferencia = bajas_ordenadas[j] - bajas_ordenadas[j-1]
            if diferencia <= tolerancia:
                grupo_actual.append(bajas_ordenadas[j])
                j += 1
            else:
                break

        # Guardar el grupo si tiene al menos 2 elementos
        if len(grupo_actual) >= 2:
            grupos.append(grupo_actual)

        # Avanzar al siguiente grupo
        i = j if j > i + 1 else i + 1

    # Retornar el grupo más grande
    if grupos:
        return max(grupos, key=len)
    return []

def calcular_baja_recomendada(bajas):
    """
    Calcula la baja recomendada según el nuevo algoritmo:
    - Si hay 2+ bajas correlativas (diferencia consecutiva ≤4%): max del grupo + 2%
    - Si todas diferentes: media + 2%
    """
    if not bajas:
        return 0

    grupo_similar = detectar_grupo_similar(bajas, tolerancia=4)

    if grupo_similar:
        # Hay un grupo de bajas correlativas
        baja_mas_alta = max(grupo_similar)
        baja_mas_baja = min(grupo_similar)
        rango = baja_mas_alta - baja_mas_baja

        # Calcular diferencias consecutivas
        grupo_ordenado = sorted(grupo_similar)
        diferencias = [f"{grupo_ordenado[i+1] - grupo_ordenado[i]:.1f}%"
                      for i in range(len(grupo_ordenado)-1)]

        baja_recomendada = baja_mas_alta + 2
        st.info(f"✅ **Grupo de {len(grupo_similar)} bajas correlativas encontrado**: {[f'{b:.1f}%' for b in grupo_ordenado]}")
        st.info(f"📏 **Diferencias consecutivas**: {' → '.join(diferencias)} (todas ≤4%)")
        st.info(f"📊 **Cálculo**: Baja más alta ({baja_mas_alta:.2f}%) + 2% = **{baja_recomendada:.2f}%**")
    else:
        # Todas diferentes, hacer media
        media = sum(bajas) / len(bajas)
        baja_recomendada = media + 2
        st.info(f"ℹ️ **No se encontró grupo correlativo** (diferencias consecutivas >4%)")
        st.info(f"📊 **Cálculo**: Media de bajas ({media:.2f}%) + 2% = **{baja_recomendada:.2f}%**")

    return baja_recomendada

def buscar_contratos(cpvs, presupuesto_min, presupuesto_max, titulo_referencia="", limit=10, ampliada=False, provincia_origen=None):
    """Buscar contratos similares con criterios específicos"""
    if isinstance(cpvs, str):
        cpvs = [cpvs]

    # Extraer primeros 4 dígitos del CPV
    cpv_patterns = []
    for cpv in cpvs[:3]:
        cpv_digits = ''.join(filter(str.isdigit, str(cpv)))
        if len(cpv_digits) >= 4:
            cpv_patterns.append(cpv_digits[:4])  # 4 dígitos

    if not cpv_patterns:
        st.warning("❌ No se pudieron extraer CPVs válidos")
        return []

    # Eliminar duplicados
    cpv_patterns = list(set(cpv_patterns))

    st.info(f"🔍 **Buscando con CPV**: {', '.join(cpv_patterns)} (primeros 4 dígitos)")

    cpv_condition = " OR ".join([f"cpv::text ~ '^{cpv}'" for cpv in cpv_patterns])

    # Presupuesto objetivo
    presupuesto_objetivo = (presupuesto_min + presupuesto_max) / 2

    # Rango de presupuesto según si es búsqueda ampliada o normal
    if ampliada:
        # ±50% del objetivo
        presupuesto_min_rango = presupuesto_objetivo * 0.5
        presupuesto_max_rango = presupuesto_objetivo * 1.5
        st.warning(f"🔄 **Búsqueda ampliada** - Rango presupuesto (±50%): €{presupuesto_min_rango:,.0f} - €{presupuesto_max_rango:,.0f}")
    else:
        # ±30% del objetivo
        presupuesto_min_rango = presupuesto_objetivo * 0.7
        presupuesto_max_rango = presupuesto_objetivo * 1.3
        st.info(f"💰 **Rango presupuesto (±30%)**: €{presupuesto_min_rango:,.0f} - €{presupuesto_max_rango:,.0f}")

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
    AND adjudicatario IS NOT NULL
    AND adjudicatario != 'null'
    AND adjudicatario != ''
    AND ({cpv_condition})
    AND importe_total BETWEEN {presupuesto_min_rango} AND {presupuesto_max_rango}
    AND ROUND(((importe_total - importe_adjudicacion) / NULLIF(importe_total, 0) * 100)::numeric, 2) > 0.5
    AND ROUND(((importe_total - importe_adjudicacion) / NULLIF(importe_total, 0) * 100)::numeric, 2) < 70
    ORDER BY fecha_publicacion DESC
    LIMIT 300
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
            results.append(contrato)

        cur.close()

        st.info(f"💾 **Contratos recuperados de BD**: {len(results)}")

        if not results:
            st.error("❌ No se encontraron contratos con ese CPV y presupuesto.")
            return []

        # FILTRAR POR SIMILITUD DE PALABRAS CLAVE
        if titulo_referencia:
            palabras_objetivo = extraer_palabras_clave(titulo_referencia)
            st.info(f"🎯 **Palabras clave del objetivo**: {', '.join(sorted(palabras_objetivo))}")

            # Calcular similitud para cada contrato
            for c in results:
                c['similitud'] = calcular_similitud_palabras(titulo_referencia, c['titulo'])

            # FILTRAR: solo contratos con al menos 1 palabra en común
            results_filtrados = [c for c in results if c['similitud'] > 0]

            st.info(f"🔍 **Contratos con palabras clave en común**: {len(results_filtrados)}")

            if not results_filtrados:
                st.warning("⚠️ No se encontraron contratos con palabras clave similares")
                st.write("**Mostrando los 5 más recientes sin filtro:**")
                results = results[:5]
                for i, c in enumerate(results, 1):
                    fecha_str = str(c['fecha_publicacion'])[:10] if c['fecha_publicacion'] else 'N/A'
                    st.write(f"{i}. [{fecha_str}] {c['titulo'][:70]}")
                return results

            results = results_filtrados

            # Calcular proximidad geográfica
            if provincia_origen:
                st.info(f"📍 **Provincia de origen**: {provincia_origen}")
                for c in results:
                    # Proximidad: 1 si coincide la provincia, 0 si no
                    provincia_contrato = c.get('provincia', '').strip().lower() if c.get('provincia') else ''
                    provincia_ref = provincia_origen.strip().lower()
                    c['proximidad'] = 1 if provincia_contrato and provincia_contrato == provincia_ref else 0
            else:
                # Sin provincia origen, todos tienen misma proximidad
                for c in results:
                    c['proximidad'] = 0

            # ORDENAR: primero por similitud, luego por proximidad geográfica, luego por fecha
            results.sort(key=lambda x: (
                x['similitud'],
                x.get('proximidad', 0),
                x['fecha_publicacion'] if x['fecha_publicacion'] else datetime(1900, 1, 1)
            ), reverse=True)

            st.success(f"✅ **Mostrando los {min(limit, len(results))} contratos más relevantes**")

            # Mostrar los primeros 10
            st.write("**Contratos encontrados (ordenados por relevancia + proximidad + recencia):**")
            for i, c in enumerate(results[:10], 1):
                fecha_str = str(c['fecha_publicacion'])[:10] if c['fecha_publicacion'] else 'N/A'
                palabras_comunes = extraer_palabras_clave(titulo_referencia).intersection(extraer_palabras_clave(c['titulo']))
                provincia_str = c.get('provincia', 'N/A')
                proximidad_icon = "📍" if c.get('proximidad', 0) == 1 else "📌"

                st.write(f"{i}. [{c['similitud']:.0%}] {proximidad_icon} [{provincia_str}] [{fecha_str}] {c['titulo'][:60]}")
                st.write(f"   💡 Palabras clave: {', '.join(sorted(palabras_comunes))}")

        else:
            # Sin título, solo ordenar por fecha
            results.sort(key=lambda x: x['fecha_publicacion'] if x['fecha_publicacion'] else datetime(1900, 1, 1), reverse=True)

        return results[:limit]

    except Exception as e:
        st.error(f"❌ Error en búsqueda: {e}")
        import traceback
        st.code(traceback.format_exc())
        return []
    finally:
        if conn:
            conn.close()

def generar_texto_informe(lote, contratos, baja_prom, baja_min, baja_max, empresas, num_lic_prom, datos):
    """Generar texto del informe para copiar siguiendo la estructura estándar"""

    # Variaciones para la introducción
    saludos = ["Buenos días,", "Buenas tardes,", "Estimados,"]
    intros_criterios = [
        "En la selección de expedientes, nos encontramos los siguientes criterios de adjudicación:",
        "En el análisis del expediente, identificamos los siguientes criterios de adjudicación:",
        "Para este proceso, se establecen los siguientes criterios de adjudicación:"
    ]

    # Variaciones para análisis de participación
    intros_participacion = [
        f"Al revisar expedientes previos de similar envergadura y presupuesto, hemos observado una participación promedio de {int(num_lic_prom)} empresa{'s' if int(num_lic_prom) != 1 else ''}.",
        f"Tras analizar licitaciones similares en cuanto a presupuesto y alcance, detectamos una concurrencia media de {int(num_lic_prom)} empresa{'s' if int(num_lic_prom) != 1 else ''}.",
        f"En expedientes comparables en presupuesto y características, observamos una participación promedio de {int(num_lic_prom)} empresa{'s' if int(num_lic_prom) != 1 else ''}."
    ]

    # Variaciones para empresas destacadas
    intros_empresas = [
        "Entre las empresas más sobresalientes en este campo están",
        "Las empresas con mayor actividad en este sector incluyen a",
        "Destacan en este ámbito empresas como"
    ]

    # Variaciones para análisis de ofertas
    analisis_ofertas = [
        f"Notamos que las variaciones en las ofertas son notables, con un promedio de entre {baja_min:.1f}% y {baja_max:.1f}%, lo que demuestra una estrategia de ofertas variada.",
        f"Observamos diferencias significativas en las propuestas económicas, oscilando entre {baja_min:.1f}% y {baja_max:.1f}%, evidenciando estrategias de competencia diversas.",
        f"Las ofertas presentadas muestran variabilidad considerable, situándose entre {baja_min:.1f}% y {baja_max:.1f}%, reflejando distintos enfoques competitivos."
    ]

    # Variaciones para recomendación
    recomendaciones = [
        f"Por ello, sugerimos una propuesta económica con un margen de descuento del {baja_prom:.1f}%.",
        f"En consecuencia, recomendamos plantear una oferta con un descuento aproximado del {baja_prom:.1f}%.",
        f"Considerando lo anterior, aconsejamos una baja cercana al {baja_prom:.1f}%."
    ]

    despedidas = ["Un cordial saludo", "Saludos cordiales", "Atentamente"]

    # Generar el texto siguiendo la estructura del ejemplo
    texto = f"{random.choice(saludos)}\n"
    texto += f"{random.choice(intros_criterios)}\n"

    # Criterios de adjudicación
    if lote['criterios']:
        for i, crit in enumerate(lote['criterios'], 1):
            desc = crit.get('descripcion', f'Criterio {i}')
            peso = crit.get('peso', '')
            if peso:
                # Limpiar el peso (quitar % si existe, etc.)
                peso_limpio = peso.strip().replace('%', '')
                texto += f"{desc.upper()}: {peso_limpio} puntos\n"
            else:
                texto += f"{desc.upper()}\n"
    else:
        texto += "OFERTA ECONÓMICA: 100 puntos\n"

    # Análisis de participación
    texto += f"{random.choice(intros_participacion)}\n"

    # Empresas destacadas
    if empresas:
        sorted_emp = sorted(empresas.items(), key=lambda x: x[1], reverse=True)[:5]
        empresas_texto = ", ".join([emp for emp, _ in sorted_emp[:-1]])
        if len(sorted_emp) > 1:
            empresas_texto += f" y {sorted_emp[-1][0]}"
        else:
            empresas_texto = sorted_emp[0][0]
        texto += f" {random.choice(intros_empresas)} {empresas_texto}.\n"

    # Análisis de ofertas
    texto += f"{random.choice(analisis_ofertas)}\n"

    # Recomendación
    texto += f"{random.choice(recomendaciones)}\n"

    # Despedida
    texto += f"{random.choice(despedidas)}\n"

    return texto

def crear_excel(datos_lote, contratos, baja_recomendada):
    """Crear archivo Excel con los resultados"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Análisis"

    # Estilos
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")

    # Título
    ws['A1'] = "ANÁLISIS DE BAJA ESTADÍSTICA"
    ws['A1'].font = Font(bold=True, size=16)
    ws.merge_cells('A1:F1')

    # Datos del contrato
    row = 3
    ws[f'A{row}'] = "Presupuesto"
    ws[f'B{row}'] = f"€{datos_lote['presupuesto']:,.2f}"
    row += 1
    ws[f'A{row}'] = "CPV"
    ws[f'B{row}'] = ', '.join(datos_lote['cpv']) if datos_lote['cpv'] else 'N/A'
    row += 2

    # Baja recomendada
    ws[f'A{row}'] = "BAJA RECOMENDADA"
    ws[f'A{row}'].font = header_font
    ws[f'A{row}'].fill = header_fill
    ws[f'B{row}'] = f"{baja_recomendada:.2f}%"
    ws[f'B{row}'].font = Font(bold=True, size=14)
    row += 2

    # Contratos similares
    ws[f'A{row}'] = "CONTRATOS SIMILARES"
    ws[f'A{row}'].font = header_font
    ws[f'A{row}'].fill = header_fill
    ws.merge_cells(f'A{row}:J{row}')
    row += 1

    # Cabeceras
    headers = ['Título', 'Organismo', 'Provincia', 'Presupuesto', 'Adjudicación', 'Baja %', 'Empresa', 'Licitadores', 'Fecha', 'CPV']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row, col, header)
        cell.font = Font(bold=True)
    row += 1

    # Datos
    for contrato in contratos:
        ws.cell(row, 1, contrato['titulo'])  # Título completo
        ws.cell(row, 2, contrato['organismo'])  # Organismo completo
        ws.cell(row, 3, contrato.get('provincia', 'N/A'))  # Provincia
        ws.cell(row, 4, contrato['importe_total'])
        ws.cell(row, 5, contrato['importe_adjudicacion'])
        ws.cell(row, 6, contrato['baja'])
        ws.cell(row, 7, contrato['empresa'])  # Empresa completa
        ws.cell(row, 8, contrato.get('numero_licitadores', 'N/A'))  # Licitadores
        fecha_pub = str(contrato['fecha_publicacion'])[:10] if contrato.get('fecha_publicacion') else 'N/A'
        ws.cell(row, 9, fecha_pub)  # Fecha
        ws.cell(row, 10, str(contrato.get('cpv', 'N/A')))  # CPV
        row += 1

    # Ajustar anchos
    ws.column_dimensions['A'].width = 60  # Título más ancho
    ws.column_dimensions['B'].width = 40  # Organismo
    ws.column_dimensions['C'].width = 15  # Provincia
    ws.column_dimensions['D'].width = 15  # Presupuesto
    ws.column_dimensions['E'].width = 15  # Adjudicación
    ws.column_dimensions['F'].width = 10  # Baja %
    ws.column_dimensions['G'].width = 40  # Empresa
    ws.column_dimensions['H'].width = 12  # Licitadores
    ws.column_dimensions['I'].width = 12  # Fecha
    ws.column_dimensions['J'].width = 20  # CPV

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

# Sistema de autenticación
def check_login():
    """Verificar si el usuario está autenticado"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔐 Acceso a Análisis de Bajas Estadísticas")
        st.markdown("---")
        st.markdown("### Introduce tus credenciales")

        with st.form("login_form"):
            email = st.text_input("Email", placeholder="usuario@empresa.com")
            password = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Iniciar Sesión")

            if submit:
                # Obtener credenciales de secrets
                valid_email = st.secrets.get("auth", {}).get("email", "")
                valid_password = st.secrets.get("auth", {}).get("password", "")

                if email == valid_email and password == valid_password:
                    st.session_state.authenticated = True
                    st.success("✅ Acceso concedido")
                    st.rerun()
                else:
                    st.error("❌ Email o contraseña incorrectos")

        st.stop()

# Verificar autenticación antes de mostrar la app
check_login()

# Interfaz principal
st.title("📊 Análisis de Bajas Estadísticas")
st.markdown("---")

# Selector de tipo de fuente
source_type = st.radio(
    "Selecciona el tipo de fuente:",
    options=["XML (URL)", "JSON (Archivo)"],
    index=0,
    help="Elige si quieres analizar desde una URL de XML o subir un archivo JSON"
)

xml_url = None
json_file = None

if source_type == "XML (URL)":
    # Input para URL del XML
    xml_url = st.text_input(
        "Introduce la URL del XML del contrato:",
        placeholder="https://contrataciondelestado.es/FileSystem/servlet/...",
        help="Pega la URL completa del XML"
    )
else:
    # File uploader para JSON
    json_file = st.file_uploader(
        "Sube el archivo JSON de la licitación:",
        type=['json'],
        help="Selecciona un archivo JSON que contenga los datos de la licitación"
    )

if st.button("🚀 Analizar Contrato", type="primary"):
    if source_type == "XML (URL)" and not xml_url:
        st.warning("Por favor, introduce una URL")
    elif source_type == "JSON (Archivo)" and not json_file:
        st.warning("Por favor, sube un archivo JSON")
    else:
        datos = None

        if source_type == "XML (URL)":
            with st.spinner("Procesando XML..."):
                datos = extraer_datos_xml_completo(xml_url)
        else:
            with st.spinner("Procesando JSON..."):
                try:
                    # Leer el archivo JSON
                    json_content = json_file.read().decode('utf-8')
                    datos = extraer_datos_json_completo(json_content)
                except Exception as e:
                    st.error(f"Error leyendo archivo JSON: {e}")
                    datos = None

        if not datos or not datos['lotes']:
            source_name = "XML" if source_type == "XML (URL)" else "JSON"
            st.error(f"No se pudieron extraer lotes del {source_name}")
        else:
            source_name = "XML" if source_type == "XML (URL)" else "JSON"
            st.success(f"✅ {source_name} procesado - {len(datos['lotes'])} lote(s) encontrado(s)")

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
                    st.markdown("### 🔍 Búsqueda de Contratos Similares")

                    pres_min = lote['presupuesto'] * 0.5
                    pres_max = lote['presupuesto'] * 1.5

                    # Búsqueda normal
                    with st.spinner("Buscando contratos..."):
                        contratos = buscar_contratos(
                            lote['cpv'],
                            pres_min,
                            pres_max,
                            titulo_referencia=lote['titulo'],
                            limit=10,
                            ampliada=False,
                            provincia_origen=datos.get('provincia')
                        )

                    # Si hay menos de 3 contratos, hacer búsqueda ampliada
                    if len(contratos) < 3:
                        st.warning(f"⚠️ Solo se encontraron {len(contratos)} contrato(s). Ampliando búsqueda...")
                        with st.spinner("Buscando con criterios ampliados (±50% presupuesto, todas las fechas)..."):
                            contratos = buscar_contratos(
                                lote['cpv'],
                                pres_min,
                                pres_max,
                                titulo_referencia=lote['titulo'],
                                limit=10,
                                ampliada=True,
                                provincia_origen=datos.get('provincia')
                            )

                        if len(contratos) < 3:
                            st.error(f"❌ Solo se encontraron {len(contratos)} contrato(s) incluso con búsqueda ampliada")

                    if contratos:
                        # Calcular estadísticas
                        bajas = [c['baja'] for c in contratos if c['baja']]

                        if bajas:
                            baja_min = min(bajas)
                            baja_max = max(bajas)

                            # Usar nuevo algoritmo de cálculo
                            baja_prom = calcular_baja_recomendada(bajas)

                            num_lic_prom = sum([c['numero_licitadores'] or 0 for c in contratos]) / len(contratos)

                            st.markdown("### 📊 Resultados")

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("🎯 Baja Recomendada", f"{baja_prom:.2f}%")
                            with col2:
                                st.metric("📈 Contratos Analizados", len(contratos))
                            with col3:
                                st.metric("👥 Licitadores Promedio", f"{num_lic_prom:.0f}")

                            st.markdown(f"**Rango de bajas:** {baja_min:.1f}% - {baja_max:.1f}%")

                            # Generar diccionario de empresas
                            empresas = {}
                            for c in contratos:
                                emp = c['empresa']
                                if emp and emp != 'N/A' and len(emp) > 3:
                                    empresas[emp] = empresas.get(emp, 0) + 1

                            # Generar texto del informe
                            texto_informe = generar_texto_informe(lote, contratos, baja_prom, baja_min, baja_max, empresas, num_lic_prom, {})

                            # Sección de descarga y texto
                            st.markdown("---")
                            st.markdown("### 📝 Informe Generado")

                            col1, col2 = st.columns([1, 1])
                            with col1:
                                excel_data = crear_excel(lote, contratos, baja_prom)
                                st.download_button(
                                    label="📥 Descargar análisis en Excel",
                                    data=excel_data,
                                    file_name=f"analisis_lote_{lote['numero']}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True
                                )
                            with col2:
                                st.info(f"✅ {len(contratos)} contratos incluidos en el análisis")

                            # Texto para copiar
                            st.markdown("#### 📄 Texto del Informe (Copia y Pega)")
                            st.text_area(
                                label="Texto completo del análisis:",
                                value=texto_informe,
                                height=300,
                                help="Copia este texto para usar en tu informe"
                            )

                            # Mostrar contratos
                            with st.expander(f"📋 Ver los {len(contratos)} contratos encontrados"):
                                for i, c in enumerate(contratos, 1):
                                    st.markdown(f"### {i}. {c['titulo']}")

                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write(f"**📍 Organismo:** {c['organismo']}")
                                        st.write(f"**🏢 Adjudicatario:** {c['empresa']}")
                                        st.write(f"**📍 Provincia:** {c.get('provincia', 'N/A')}")
                                        st.write(f"**🔢 CPV:** {c.get('cpv', 'N/A')}")
                                    with col2:
                                        st.write(f"**💰 Presupuesto:** €{c['importe_total']:,.2f}")
                                        st.write(f"**💵 Adjudicación:** €{c['importe_adjudicacion']:,.2f}")
                                        st.write(f"**📉 Baja:** {c['baja']:.2f}%")
                                        fecha = str(c['fecha_publicacion'])[:10] if c['fecha_publicacion'] else 'N/A'
                                        st.write(f"**📅 Fecha:** {fecha}")
                                        num_lic = c.get('numero_licitadores', 'N/A')
                                        st.write(f"**👥 Licitadores:** {num_lic if num_lic else 'N/A'}")

                                    st.divider()
                else:
                    st.warning("⚠️ No se pudo extraer CPV o presupuesto del lote")

st.markdown("---")
st.caption("📊 Análisis basado en datos del Portal de Contratación del Estado")
