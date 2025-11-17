#!/usr/bin/env python3
"""
Script para probar la conexión a la base de datos PostgreSQL
"""
import psycopg2

def test_postgres_connection():
    """Probar conexión a la base de datos PostgreSQL"""
    print("🔍 Intentando conectar a PostgreSQL...")
    print("-" * 50)

    config = {
        'host': '195.154.137.88',
        'port': 55432,
        'user': 'metabase',
        'password': 'Oclem1010*',
        'database': 'oclemconcursos'
    }

    try:
        print(f"Host: {config['host']}")
        print(f"Puerto: {config['port']}")
        print(f"Usuario: {config['user']}")
        print(f"Base de datos: {config['database']}")
        print("-" * 50)

        # Intentar conexión
        connection = psycopg2.connect(**config)

        print("✅ ¡Conexión exitosa a PostgreSQL!")

        # Obtener información del servidor
        cursor = connection.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"\n📊 Versión de PostgreSQL: {version[0]}")

        # Obtener lista de tablas
        cursor.execute("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)
        tables = cursor.fetchall()

        print(f"\n📋 Tablas disponibles ({len(tables)}):")
        for i, table in enumerate(tables, 1):
            print(f"  {i}. {table[0]}")

        cursor.close()
        connection.close()
        print("\n✅ Conexión cerrada correctamente")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_postgres_connection()
