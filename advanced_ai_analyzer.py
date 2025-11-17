import mysql.connector
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')

class AdvancedDatabaseAnalyzer:
    def __init__(self):
        self.connection = None
        self.tables = []

    def connect_to_database(self):
        """Conectar a la base de datos MySQL"""
        try:
            self.connection = mysql.connector.connect(
                host=st.secrets["mysql"]["host"],
                port=st.secrets["mysql"]["port"],
                user=st.secrets["mysql"]["user"],
                password=st.secrets["mysql"]["password"],
                database=st.secrets["mysql"]["database"]
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
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        cursor.close()
        return tables

    def get_table_structure(self, table_name):
        """Obtener estructura de una tabla"""
        cursor = self.connection.cursor()
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        cursor.close()
        return columns

    def get_table_data(self, table_name, limit=1000, where_clause=""):
        """Obtener datos de una tabla con filtros opcionales"""
        query = f"SELECT * FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        query += f" LIMIT {limit}"
        return pd.read_sql(query, self.connection)

    def execute_custom_query(self, query):
        """Ejecutar consulta personalizada"""
        try:
            return pd.read_sql(query, self.connection)
        except Exception as e:
            st.error(f"Error ejecutando consulta: {e}")
            return pd.DataFrame()

    def ai_data_insights(self, data, analysis_type):
        """Análisis de datos con IA"""
        insights = {}

        numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = data.select_dtypes(include=['object']).columns.tolist()

        if analysis_type == "clustering":
            insights = self.perform_clustering(data, numeric_cols)
        elif analysis_type == "trends":
            insights = self.analyze_trends(data, numeric_cols)
        elif analysis_type == "anomalies":
            insights = self.detect_anomalies(data, numeric_cols)
        elif analysis_type == "predictions":
            insights = self.make_predictions(data, numeric_cols)
        elif analysis_type == "correlations":
            insights = self.analyze_correlations(data, numeric_cols)

        return insights

    def perform_clustering(self, data, numeric_cols):
        """Realizar clustering de datos"""
        if len(numeric_cols) < 2:
            return {"error": "Se necesitan al menos 2 columnas numéricas para clustering"}

        # Preparar datos
        cluster_data = data[numeric_cols].dropna()
        if len(cluster_data) < 5:
            return {"error": "Datos insuficientes para clustering"}

        # Escalar datos
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(cluster_data)

        # Encontrar número óptimo de clusters
        inertias = []
        K_range = range(2, min(11, len(cluster_data)))

        for k in K_range:
            kmeans = KMeans(n_clusters=k, random_state=42)
            kmeans.fit(scaled_data)
            inertias.append(kmeans.inertia_)

        # Usar k=3 por defecto
        optimal_k = 3 if len(K_range) >= 3 else max(K_range)

        kmeans = KMeans(n_clusters=optimal_k, random_state=42)
        clusters = kmeans.fit_predict(scaled_data)

        cluster_data['Cluster'] = clusters

        return {
            "cluster_data": cluster_data,
            "num_clusters": optimal_k,
            "cluster_centers": kmeans.cluster_centers_,
            "inertias": inertias,
            "K_range": list(K_range)
        }

    def analyze_trends(self, data, numeric_cols):
        """Analizar tendencias en los datos"""
        trends = {}

        for col in numeric_cols:
            if data[col].notna().sum() > 1:
                # Calcular tendencia usando regresión lineal
                x = np.arange(len(data)).reshape(-1, 1)
                y = data[col].fillna(data[col].mean())

                model = LinearRegression()
                model.fit(x, y)

                trend_direction = "Creciente" if model.coef_[0] > 0 else "Decreciente"
                trend_strength = abs(model.coef_[0])

                trends[col] = {
                    "direction": trend_direction,
                    "strength": trend_strength,
                    "r_squared": model.score(x, y)
                }

        return trends

    def detect_anomalies(self, data, numeric_cols):
        """Detectar anomalías usando IQR"""
        anomalies = {}

        for col in numeric_cols:
            if data[col].notna().sum() > 3:
                Q1 = data[col].quantile(0.25)
                Q3 = data[col].quantile(0.75)
                IQR = Q3 - Q1

                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                outliers = data[(data[col] < lower_bound) | (data[col] > upper_bound)]

                anomalies[col] = {
                    "count": len(outliers),
                    "percentage": (len(outliers) / len(data)) * 100,
                    "outliers": outliers[col].tolist(),
                    "bounds": {"lower": lower_bound, "upper": upper_bound}
                }

        return anomalies

    def make_predictions(self, data, numeric_cols):
        """Hacer predicciones usando Random Forest"""
        if len(numeric_cols) < 2:
            return {"error": "Se necesitan al menos 2 columnas numéricas para predicciones"}

        predictions = {}

        for target_col in numeric_cols[:2]:  # Limitar a 2 predicciones
            feature_cols = [col for col in numeric_cols if col != target_col]

            if len(feature_cols) == 0:
                continue

            # Preparar datos
            clean_data = data[feature_cols + [target_col]].dropna()

            if len(clean_data) < 10:
                continue

            X = clean_data[feature_cols]
            y = clean_data[target_col]

            # Dividir datos
            split_point = int(len(clean_data) * 0.8)
            X_train, X_test = X[:split_point], X[split_point:]
            y_train, y_test = y[:split_point], y[split_point:]

            if len(X_test) == 0:
                continue

            # Entrenar modelo
            model = RandomForestRegressor(n_estimators=50, random_state=42)
            model.fit(X_train, y_train)

            # Hacer predicciones
            y_pred = model.predict(X_test)

            predictions[target_col] = {
                "mse": mean_squared_error(y_test, y_pred),
                "r2": r2_score(y_test, y_pred),
                "feature_importance": dict(zip(feature_cols, model.feature_importances_)),
                "predictions": y_pred.tolist(),
                "actual": y_test.tolist()
            }

        return predictions

    def analyze_correlations(self, data, numeric_cols):
        """Analizar correlaciones entre variables"""
        if len(numeric_cols) < 2:
            return {"error": "Se necesitan al menos 2 columnas numéricas para correlaciones"}

        corr_matrix = data[numeric_cols].corr()

        # Encontrar correlaciones más fuertes
        strong_correlations = []

        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                corr_value = corr_matrix.iloc[i, j]
                if abs(corr_value) > 0.5:  # Correlación fuerte
                    strong_correlations.append({
                        "var1": corr_matrix.columns[i],
                        "var2": corr_matrix.columns[j],
                        "correlation": corr_value,
                        "strength": "Fuerte" if abs(corr_value) > 0.8 else "Moderada"
                    })

        return {
            "correlation_matrix": corr_matrix,
            "strong_correlations": strong_correlations
        }

def create_visualizations(insights, analysis_type):
    """Crear visualizaciones basadas en el tipo de análisis"""

    if analysis_type == "clustering" and "cluster_data" in insights:
        cluster_data = insights["cluster_data"]
        numeric_cols = [col for col in cluster_data.columns if col != 'Cluster']

        if len(numeric_cols) >= 2:
            fig = px.scatter(cluster_data, x=numeric_cols[0], y=numeric_cols[1],
                           color='Cluster', title="Análisis de Clusters")
            st.plotly_chart(fig)

        # Gráfico del método del codo
        if "inertias" in insights:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=list(insights["K_range"]), y=insights["inertias"],
                                   mode='lines+markers', name='Inercia'))
            fig.update_layout(title="Método del Codo para Clustering",
                            xaxis_title="Número de Clusters",
                            yaxis_title="Inercia")
            st.plotly_chart(fig)

    elif analysis_type == "trends":
        for col, trend_info in insights.items():
            st.write(f"**{col}**: {trend_info['direction']} (R² = {trend_info['r_squared']:.3f})")

    elif analysis_type == "anomalies":
        for col, anomaly_info in insights.items():
            if anomaly_info["count"] > 0:
                st.write(f"**{col}**: {anomaly_info['count']} anomalías ({anomaly_info['percentage']:.1f}%)")

    elif analysis_type == "predictions":
        for target, pred_info in insights.items():
            st.write(f"**Predicción para {target}**: R² = {pred_info['r2']:.3f}")

            # Gráfico de importancia de características
            features = list(pred_info['feature_importance'].keys())
            importance = list(pred_info['feature_importance'].values())

            fig = px.bar(x=importance, y=features, orientation='h',
                        title=f"Importancia de Características para {target}")
            st.plotly_chart(fig)

    elif analysis_type == "correlations" and "correlation_matrix" in insights:
        corr_matrix = insights["correlation_matrix"]
        fig = px.imshow(corr_matrix, title="Matriz de Correlación",
                       color_continuous_scale="RdBu", aspect="auto")
        st.plotly_chart(fig)

        if insights["strong_correlations"]:
            st.write("**Correlaciones Fuertes:**")
            for corr in insights["strong_correlations"]:
                st.write(f"- {corr['var1']} ↔ {corr['var2']}: {corr['correlation']:.3f} ({corr['strength']})")

def main():
    st.title("🤖 Analizador Avanzado de Datos con IA")
    st.sidebar.title("Configuración Avanzada")

    # Inicializar analizador
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = AdvancedDatabaseAnalyzer()

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
            # Parámetros de análisis
            st.sidebar.subheader("Parámetros de Análisis")

            # Filtros
            where_clause = st.sidebar.text_input("Filtro WHERE (opcional):", placeholder="columna = 'valor'")
            limit = st.sidebar.number_input("Límite de registros:", min_value=100, max_value=10000, value=1000)

            # Tipo de análisis de IA
            analysis_type = st.sidebar.selectbox("Tipo de Análisis de IA:", [
                "correlations", "clustering", "trends", "anomalies", "predictions"
            ])

            # Cargar datos
            if st.button(f"🚀 Analizar {selected_table} con IA"):
                with st.spinner("Cargando y analizando datos..."):
                    data = analyzer.get_table_data(selected_table, limit, where_clause)

                    if not data.empty:
                        st.subheader(f"📊 Análisis de {selected_table}")
                        st.write(f"Total de registros analizados: {len(data)}")

                        # Mostrar muestra de datos
                        with st.expander("Ver muestra de datos"):
                            st.dataframe(data.head(10))

                        # Análisis de IA
                        st.subheader(f"🤖 Análisis de IA: {analysis_type.title()}")

                        insights = analyzer.ai_data_insights(data, analysis_type)

                        if "error" in insights:
                            st.error(insights["error"])
                        else:
                            create_visualizations(insights, analysis_type)

    # Sección de consultas personalizadas avanzadas
    st.sidebar.subheader("💡 Consulta + Análisis IA")
    custom_query = st.sidebar.text_area("Consulta SQL personalizada:")

    if custom_query:
        ai_analysis = st.sidebar.selectbox("Análisis IA automático:", [
            "correlations", "clustering", "trends", "anomalies"
        ])

        if st.sidebar.button("Ejecutar y Analizar"):
            with st.spinner("Ejecutando consulta y análisis..."):
                result = analyzer.execute_custom_query(custom_query)
                if not result.empty:
                    st.subheader("📋 Resultado de la consulta")
                    st.dataframe(result)

                    # Análisis automático con IA
                    st.subheader(f"🤖 Análisis de IA: {ai_analysis.title()}")
                    insights = analyzer.ai_data_insights(result, ai_analysis)

                    if "error" not in insights:
                        create_visualizations(insights, ai_analysis)

if __name__ == "__main__":
    main()