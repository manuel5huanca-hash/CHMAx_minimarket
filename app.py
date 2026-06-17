from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "clave_secreta_segura"  # 👈 Necesario para manejar sesiones

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///productos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo de Producto
class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    imagen = db.Column(db.String(100), nullable=True)
    categoria = db.Column(db.String(50), nullable=True)

# ------------------ RUTAS PRINCIPALES ------------------

@app.route('/')
def index():
    productos = Producto.query.all()
    return render_template('index.html', productos=productos)

@app.route('/catalogo/<categoria>')
def catalogo(categoria):
    productos = Producto.query.filter_by(categoria=categoria).all()
    return render_template('catalogo.html', categoria=categoria, productos=productos)

@app.route('/dashboard')
def dashboard():
    if session.get('usuario') != "Administrador":
        return redirect(url_for('login'))

    # Productos
    productos = Producto.query.all()

    # Leer mensajes de contactenos.txt
    mensajes = []
    try:
        with open('contactenos.txt', 'r', encoding='utf-8') as archivo:
            for linea in archivo:
                partes = linea.strip().split('|')
                if len(partes) == 6:
                    mensajes.append({
                        'nombre': partes[0],
                        'lugar': partes[1],
                        'equipo': partes[2],
                        'mensaje': partes[3],
                        'numero': partes[4],
                        'correo': partes[5]
                    })
    except FileNotFoundError:
        pass

    # Renderizar dashboard con productos y mensajes
    return render_template('dashboard.html', productos=productos, mensajes=mensajes)




# ------------------ REGISTRO / LOGIN ------------------

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        contraseña = request.form['contraseña']

        with open('usuarios.txt', 'a') as archivo:
            archivo.write(f"{nombre},{correo},{contraseña}\n")

        return redirect(url_for('login'))
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        contraseña = request.form['contraseña']

        # Admin
        if correo == 'admin' and contraseña == 'admin':
            session['usuario'] = 'Administrador'
            return redirect(url_for('dashboard'))

        # Usuarios registrados
        try:
            with open('usuarios.txt', 'r') as archivo:
                for linea in archivo:
                    partes = linea.strip().split(',')
                    if len(partes) == 3:
                        nombre, email, clave = partes
                        if correo == email and contraseña == clave:
                            session['usuario'] = nombre
                            return redirect(url_for('index'))
        except FileNotFoundError:
            pass

        return render_template('login.html', error="Credenciales incorrectas.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('index'))

# ------------------ BUSCADOR ------------------

@app.route('/buscar', methods=['GET'])
def buscar():
    termino = request.args.get('q', '').strip().lower()
    resultados = []

    if termino:
        resultados = Producto.query.filter(Producto.nombre.ilike(f"%{termino}%")).all()

    mensaje = None if resultados else f"No se encontraron productos relacionados con '{termino}'. Por el momento no tenemos ese producto disponible."
    return render_template('buscar.html', termino=termino, resultados=resultados, mensaje=mensaje)

# ------------------ CARRITO ------------------

@app.route('/carrito')
def carrito():
    carrito = session.get('carrito', [])
    # Calcula el total multiplicando precio × cantidad
    total = sum(item['precio'] * item['cantidad'] for item in carrito)
    return render_template('carrito.html', carrito=carrito, total=total)


@app.route('/agregar_carrito/<int:id>', methods=['GET', 'POST'])
def agregar_carrito(id):
    producto = Producto.query.get_or_404(id)
    # Captura cantidad desde query string o formulario, por defecto 1
    cantidad = int(request.args.get('cantidad', 1))

    carrito = session.get('carrito', [])

    # Si el producto ya está en el carrito, ajusta la cantidad
    for item in carrito:
        if item['id'] == producto.id:
            item['cantidad'] += cantidad
            # Si la cantidad llega a 0 o menos, elimina el producto
            if item['cantidad'] <= 0:
                carrito = [i for i in carrito if i['id'] != producto.id]
            break
    else:
        # Si no existe en el carrito, lo agrega
        carrito.append({
            'id': producto.id,
            'nombre': producto.nombre,
            'precio': producto.precio,
            'cantidad': cantidad
        })

    session['carrito'] = carrito
    return redirect(url_for('carrito'))


@app.route('/eliminar_carrito/<int:id>')
def eliminar_carrito(id):
    carrito = session.get('carrito', [])
    # Filtra todos los productos excepto el que se quiere eliminar
    carrito = [item for item in carrito if item['id'] != id]
    session['carrito'] = carrito
    return redirect(url_for('carrito'))

# ------------------ CRUD PRODUCTOS ------------------

import os
from werkzeug.utils import secure_filename

@app.route('/producto/nuevo', methods=['GET', 'POST'])
def nuevo_producto():
    if session.get('usuario') != "Administrador":
        return redirect(url_for('login'))

    if request.method == 'POST':
        nombre = request.form['nombre']
        precio = float(request.form['precio'])
        stock = int(request.form['stock'])
        categoria = request.form['categoria']

        # Manejo de imagen subida
        imagen_archivo = request.files['imagen']
        nombre_imagen = None
        if imagen_archivo and imagen_archivo.filename != '':
            nombre_imagen = secure_filename(imagen_archivo.filename)
            ruta_imagen = os.path.join('static', 'img', 'productos', nombre_imagen)
            imagen_archivo.save(ruta_imagen)

        producto = Producto(
            nombre=nombre,
            precio=precio,
            stock=stock,
            categoria=categoria,
            imagen=nombre_imagen
        )
        db.session.add(producto)
        db.session.commit()
        return redirect(url_for('dashboard'))

    return render_template('nuevo_producto.html')


@app.route('/producto/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    if session.get('usuario') != "Administrador":
        return redirect(url_for('login'))
    producto = Producto.query.get_or_404(id)
    if request.method == 'POST':
        producto.nombre = request.form['nombre']
        producto.precio = float(request.form['precio'])
        producto.stock = int(request.form['stock'])
        producto.categoria = request.form['categoria']
        producto.imagen = request.form['imagen']
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('editar_producto.html', producto=producto)


@app.route('/producto/eliminar/<int:id>')
def eliminar_producto(id):
    if session.get('usuario') != "Administrador":
        return redirect(url_for('login'))
    producto = Producto.query.get_or_404(id)
    db.session.delete(producto)
    db.session.commit()
    return redirect(url_for('dashboard'))

# ------------------ contactenos ------------------
@app.route('/contactenos', methods=['GET', 'POST'])
def contactenos():
    if request.method == 'POST':
        nombre = request.form['nombre']
        lugar = request.form['lugar']
        equipo = request.form['equipo']
        otro_equipo = request.form.get('otro_equipo', '')
        mensaje = request.form['mensaje']
        numero = request.form['numero']
        correo = request.form['correo']

        # Guardar en archivo contactenos.txt
        with open('contactenos.txt', 'a', encoding='utf-8') as archivo:
            archivo.write(f"{nombre}|{lugar}|{equipo if equipo != 'Otro' else otro_equipo}|{mensaje}|{numero}|{correo}\n")

        # Mostrar confirmación en pantalla
        return render_template('contactenos.html', enviado=True)

    # Si es GET, solo muestra el formulario
    return render_template('contactenos.html', enviado=False)







# ------------------ INICIALIZACIÓN ------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Producto.query.first():
            productos_iniciales = [
                # Laptops
                Producto(nombre="Laptop ASUS Vivobook", precio=2399.00, stock=10, imagen="Asus_vivo.jpg", categoria="laptops"),
                Producto(nombre="Laptop Lenovo ThinkPad", precio=2999.00, stock=8, imagen="lenovo_thinpad.jpg", categoria="laptops"),
                Producto(nombre="Laptop HP Pavilion", precio=2599.00, stock=6, imagen="hp_pavilion.jpg", categoria="laptops"),

                # PC Gamer
                Producto(nombre="PC Gamer Ryzen 5", precio=3499.00, stock=5, imagen="pc_ryzen5.jpg", categoria="gamer"),
                Producto(nombre="PC Gamer Intel i7", precio=4299.00, stock=3, imagen="pc_corei7.jpg", categoria="gamer"),
                Producto(nombre="PC Gamer RTX 3060", precio=4799.00, stock=4, imagen="pc_rtx.jpg", categoria="gamer"),

                # Oficina
                Producto(nombre="PC Oficina HP", precio=1599.00, stock=12, imagen="pc_oficina_hp.jpg", categoria="oficina"),
                Producto(nombre="PC Oficina Dell", precio=1799.00, stock=9, imagen="pc_oficina_dell.jpg", categoria="oficina"),
                Producto(nombre="PC Oficina Lenovo", precio=1699.00, stock=7, imagen="pc_oficina_lenovo.jpg", categoria="oficina"),

                # Ingeniería & Diseño
                Producto(nombre="Workstation Ingeniería", precio=5999.00, stock=2, imagen="pc_ingenieria.jpg", categoria="ingenieria"),
                Producto(nombre="PC Diseño Gráfico", precio=5499.00, stock=4, imagen="pc_diseño_grafico.jpg", categoria="ingenieria"),
                Producto(nombre="PC Arquitectura 3D", precio=6299.00, stock=3, imagen="pc_arquitectura.jpg", categoria="ingenieria"),

                # Monitores
                Producto(nombre="Monitor LG 24'' Full HD", precio=699.00, stock=10, imagen="monitor1.jpg", categoria="monitores"),
                Producto(nombre="Monitor Samsung Curvo 27''", precio=999.00, stock=6, imagen="monitor2.jpg", categoria="monitores"),
                Producto(nombre="Monitor ASUS ProArt 32''", precio=1499.00, stock=4, imagen="monitor3.jpg", categoria="monitores"),

                # Accesorios
                Producto(nombre="Teclado Mecánico RGB", precio=299.00, stock=15, imagen="accesorio4.jpg", categoria="accesorios"),
                Producto(nombre="Mouse Gamer Logitech", precio=199.00, stock=20, imagen="accesorio2.jpg", categoria="accesorios"),
                Producto(nombre="Auriculares HyperX Cloud", precio=399.00, stock=10, imagen="accesorio3.jpg", categoria="accesorios"),
                Producto(nombre="Webcam Full HD", precio=249.00, stock=8, imagen="accesorio5.jpg", categoria="accesorios"),
                Producto(nombre="Micrófono USB Blue Snowball", precio=349.00, stock=5, imagen="accesorio1.jpg", categoria="accesorios"),
            ]
            db.session.bulk_save_objects(productos_iniciales)
            db.session.commit()

    app.run(host='0.0.0.0', port=5000, debug=True)
