import os
import logging
import pymysql
from flask import Flask, jsonify, request
from flask_cors import CORS
from config import get_db_config

# ── App setup ─────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from web tier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)s  %(message)s'
)
log = logging.getLogger(__name__)

# ── Database connection helper ─────────────────────────────────────────
def get_connection(read_only=False):
    """
    Returns a database connection.
    read_only=True  → Aurora Reader endpoint (SELECT queries)
    read_only=False → Aurora Writer endpoint (INSERT/UPDATE/DELETE)
    """
    cfg  = get_db_config()
    host = cfg['reader_host'] if read_only else cfg['writer_host']

    return pymysql.connect(
        host=host,
        user=cfg['username'],
        password=cfg['password'],
        database=cfg['dbname'],
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30
    )

# ── Health check — used by Internal ALB every 30 seconds ──────────────
@app.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy',
        'tier':   'app',
        'host':   os.environ.get('HOSTNAME', 'unknown')
    }), 200

# ── GET all products ───────────────────────────────────────────────────
@app.route('/api/products', methods=['GET'])
def get_products():
    try:
        conn = get_connection(read_only=True)  # Reader endpoint
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id, name, description, price, stock, created_at '
                'FROM products ORDER BY id'
            )
            products = cur.fetchall()
        conn.close()
        # Convert Decimal to float for JSON serialisation
        for p in products:
            p['price'] = float(p['price'])
            if p['created_at']:
                p['created_at'] = str(p['created_at'])
        return jsonify({'products': products, 'count': len(products)}), 200

    except Exception as e:
        log.error(f'get_products error: {e}')
        return jsonify({'error': 'Database error'}), 500

# ── GET single product ─────────────────────────────────────────────────
@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    try:
        conn = get_connection(read_only=True)
        with conn.cursor() as cur:
            cur.execute(
                'SELECT * FROM products WHERE id = %s',
                (product_id,)
            )
            product = cur.fetchone()
        conn.close()

        if not product:
            return jsonify({'error': 'Product not found'}), 404

        product['price'] = float(product['price'])
        product['created_at'] = str(product['created_at'])
        return jsonify(product), 200

    except Exception as e:
        log.error(f'get_product error: {e}')
        return jsonify({'error': str(e)}), 500

# ── POST create product ────────────────────────────────────────────────
@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400
    if not data.get('name') or not data.get('price'):
        return jsonify({'error': 'name and price are required'}), 400

    try:
        conn = get_connection(read_only=False)  # Writer endpoint
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO products (name, description, price, stock) '
                'VALUES (%s, %s, %s, %s)',
                (
                    data['name'],
                    data.get('description', ''),
                    data['price'],
                    data.get('stock', 0)
                )
            )
            conn.commit()
            new_id = cur.lastrowid
        conn.close()
        return jsonify({'id': new_id, 'message': 'Product created'}), 201

    except Exception as e:
        log.error(f'create_product error: {e}')
        return jsonify({'error': str(e)}), 500

# ── DELETE product ─────────────────────────────────────────────────────
@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        conn = get_connection(read_only=False)
        with conn.cursor() as cur:
            cur.execute('DELETE FROM products WHERE id = %s', (product_id,))
            conn.commit()
            affected = cur.rowcount
        conn.close()

        if affected == 0:
            return jsonify({'error': 'Product not found'}), 404
        return jsonify({'message': 'Product deleted'}), 200

    except Exception as e:
        log.error(f'delete_product error: {e}')
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Development only — production uses gunicorn
    app.run(host='0.0.0.0', port=5000, debug=False)