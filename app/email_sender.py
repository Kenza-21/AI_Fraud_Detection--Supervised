import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText # <-- LIGNE CORRIGÉE
from email.mime.base import MIMEBase
from email import encoders
import os
from dotenv import load_dotenv

def send_email_with_report(to_email, report_path, subject, body):
    # Configuration du serveur SMTP
    load_dotenv()
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT"))
    sender_email = os.getenv("SENDER_EMAIL")
    password = os.getenv("PASSWORD")


    # Création du message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject

    # Ajout du corps du message
    msg.attach(MIMEText(body, 'plain'))

    # Ajout du fichier en pièce jointe
    with open(report_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f"attachment; filename= {report_path}",
    )
    msg.attach(part)

    try:
        # Connexion au serveur
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Démarrer le chiffrement TLS
        server.login(sender_email, password)
        
        # Envoi de l'email
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        
        server.quit()
        print("Email envoyé avec succès !")
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email: {e}")
        return False