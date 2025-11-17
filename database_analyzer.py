import psycopg2
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class DatabaseAnalyzer:
    def __init__(self):
        self.connection = None
        self.tables = []

    def connect_to_database(self):
        """Conectar a la base de datos PostgreSQL"""
        try:
            self.connection = psycopg2.connect(
                host=st.secrets["postgres"]["host"],
                port=st.secrets["postgres"]["port"],
                user=st.secrets["postgres"]["user"],
                password=st.secrets["postgres"]["password"],
                database=st.secrets["postgres"]["database"]
            )
            return True
        except Exception as e:
            st.error(f"Error conectando a la base de datos: {e}")
            return False

    def get_tables(self):
        """Obtener lista de tablas disponibles"""
        if not self.connection:
            return []

        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)
        tables = [table[0] for table in cursor.fetchall()]
        cursor.close()
        return tables

    def get_table_structure(self, table_name):
        """Obtener estructura de una tabla"""
        cursor = self.connection.cursor()
        cursor.execute(f"""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
        """)
        columns = cursor.fetchall()
        cursor.close()
        return columns

    def get_table_data(self, table_name, limit=1000):
        """Obtener datos de una tabla"""
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        return pd.read_sql(query, self.connection)

    def execute_custom_query(self, query):
        """Ejecutar consulta personalizada"""
        try:
            return pd.read_sql(query, self.connection)
        except Exception as e:
            st.error(f"Error ejecutando consulta: {e}")
            return pd.DataFrame()

def main():
    st.title("🤖 Analizador de Datos con IA")
    st.sidebar.title("Configuración")

    # Inicializar analizador
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = DatabaseAnalyzer()

    analyzer = st.session_state.analyzer

    # Conectar a la base de datos
    if not analyzer.connection:
        with st.spinner("Conectando a la base de datos..."):
            if analyzer.connect_to_database():
                st.success("✅ Conectado exitosamente a la base de datos")
                st.session_state.tables = analyzer.get_tables()
            else:
                st.error("❌ No se pudo conectar a la base de datos")
                return

    # Mostrar tablas disponibles
    if hasattr(st.session_state, 'tables'):
        st.sidebar.subheader("Tablas disponibles:")
        selected_table = st.sidebar.selectbox("Selecciona una tabla:", st.session_state.tables)

        if selected_table:
            # Mostrar estructura de la tabla
            with st.expander(f"📋 Estructura de {selected_table}"):
                structure = analyzer.get_table_structure(selected_table)
                structure_df = pd.DataFrame(structure, columns=['Campo', 'Tipo', 'Null', 'Default'])
                st.dataframe(structure_df)

            # Cargar datos
            if st.button(f"🔍 Explorar datos de {selected_table}"):
                with st.spinner("Cargando datos..."):
                    data = analyzer.get_table_data(selected_table)

                    if not data.empty:
                        st.subheader(f"📊 Datos de {selected_table}")
                        st.write(f"Total de registros: {len(data)}")

                        # Mostrar muestra de datos
                        st.dataframe(data.head(10))

                        # Análisis automático básico
                        st.subheader("📈 Análisis Automático")

                        # Estadísticas básicas para columnas numéricas
                        numeric_cols = data.select_dtypes(include=[np.number]).columns
                        if len(numeric_cols) > 0:
                            st.write("**Estadísticas numéricas:**")
                            st.dataframe(data[numeric_cols].describe())

                        # Gráficos automáticos
                        if len(numeric_cols) > 0:
                            col1, col2 = st.columns(2)

                            with col1:
                                # Histograma de la primera columna numérica
                                first_numeric = numeric_cols[0]
                                fig = px.histogram(data, x=first_numeric, title=f"Distribución de {first_numeric}")
                                st.plotly_chart(fig)

                            with col2:
                                # Gráfico de correlación si hay más de una columna numérica
                                if len(numeric_cols) > 1:
                                    corr_matrix = data[numeric_cols].corr()
                                    fig = px.imshow(corr_matrix, title="Matriz de Correlación")
                                    st.plotly_chart(fig)

    # Sección de consultas personalizadas
    st.sidebar.subheader("💡 Consulta Personalizada")
    custom_query = st.sidebar.text_area("Escribe tu consulta SQL:")

    if st.sidebar.button("Ejecutar Consulta"):
        if custom_query:
            with st.spinner("Ejecutando consulta..."):
                result = analyzer.execute_custom_query(custom_query)
                if not result.empty:
                    st.subheader("📋 Resultado de la consulta")
                    st.dataframe(result)

                    # Análisis automático del resultado
                    numeric_cols = result.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) > 0:
                        st.subheader("📊 Visualización automática")
                        for col in numeric_cols[:3]:  # Máximo 3 gráficos
                            fig = px.box(result, y=col, title=f"Distribución de {col}")
                            st.plotly_chart(fig)

if __name__ == "__main__":
    main()