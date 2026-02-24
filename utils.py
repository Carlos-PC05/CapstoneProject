from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask import current_app, url_for
from huey import SqliteHuey

huey = SqliteHuey(filename='instance/huey.db')

mail = Mail()

@huey.task()
def send_async_email(subject, recipient, template, sender, mail_config):
    """
    Tarea de Huey para enviar correo de forma asíncrona.
    Recibe los parámetros necesarios para reconstruir el contexto o enviar el correo.
    Nota: Flask-Mail requiere contexto de aplicación.
    """
    # Creamos una app mínima o usamos el contexto si es posible, 
    # pero con Huey lo ideal es pasar configuración explícita o 
    # importar 'app' desde donde se inicializa (cuidado con importaciones circulares).
    # Para simplificar y evitar ciclos, usaremos la instancia 'mail' y crearemos un contexto manual
    # O mejor: importamos app dentro de la función para evitar ciclo al inicio
    from app import app
    
    with app.app_context():
        try:
            msg = Message(
                subject,
                recipients=[recipient],
                html=template,
                sender=sender
            )
            mail.send(msg)
            print(f"Email enviado a {recipient} via Huey")
        except Exception as e:
            print(f"Error enviando email con Huey: {e}")
            raise e # Para que Huey sepa que falló y pueda reintentar si se configura

def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])

def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
    except:
        return False
    return email

def send_email(to, subject, template):
    """
    Encola la tarea de envío de correo en Huey.
    """
    app = current_app._get_current_object()
    sender = app.config['MAIL_DEFAULT_SENDER']
    
    # Encolar tarea
    # Pasamos solo datos serializables (strings, ints, dicts), no objetos complejos como 'app'
    send_async_email(subject, to, template, sender, None)
    
    return True
