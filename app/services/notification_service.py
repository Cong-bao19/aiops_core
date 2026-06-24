import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import asyncio

class NotificationService:
    
    SENDER_EMAIL = "bao1962004@gmail.com"  # Email gửi
    SENDER_PASSWORD = "fhfv zxvq arqv bzil"      # Mật khẩu ứng dụng 
    RECEIVER_EMAIL = "bao1962004@gmail.com" #email  test

    @staticmethod
    def _send_email_sync(subject: str, html_content: str):
        """Hàm đồng bộ xử lý việc kết nối SMTP và gửi mail"""
        

        msg = MIMEMultipart()
        msg['From'] = NotificationService.SENDER_EMAIL
        msg['To'] = NotificationService.RECEIVER_EMAIL
        msg['Subject'] = subject

        msg.attach(MIMEText(html_content, 'html'))

        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls() 
            server.login(NotificationService.SENDER_EMAIL, NotificationService.SENDER_PASSWORD)
            server.send_message(msg)
            server.quit()
            print("  [EMAIL] Đã bắn cảnh báo sự cố qua Email thành công!")
        except Exception as e:
            print(f"  [EMAIL ERROR] Không thể gửi email: {e}")

    @staticmethod
    async def trigger_alerts(trace_id: str, service_name: str, severity: str, ai_prediction: str):
        """Logic phân luồng gọi cảnh báo"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if severity == "CRITICAL" or severity == "HIGH":
            subject = f" [CRITICAL ALERT] Sự cố phát hiện tại {service_name}"
            
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="border: 2px solid #dc2626; padding: 20px; border-radius: 8px; background-color: #fef2f2;">
                        <h2 style="color: #dc2626; margin-top: 0;"> CRITICAL INCIDENT DETECTED!</h2>
                        <p>Hệ thống AIOps vừa phát hiện một hành vi bất thường nghiêm trọng.</p>
                        <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                            <tr><td style="padding: 8px; border-bottom: 1px solid #fca5a5;"><b>Service:</b></td><td style="padding: 8px; border-bottom: 1px solid #fca5a5;">{service_name}</td></tr>
                            <tr><td style="padding: 8px; border-bottom: 1px solid #fca5a5;"><b>Time:</b></td><td style="padding: 8px; border-bottom: 1px solid #fca5a5;">{now_str}</td></tr>
                            <tr><td style="padding: 8px; border-bottom: 1px solid #fca5a5;"><b>AI Diagnosis:</b></td><td style="padding: 8px; border-bottom: 1px solid #fca5a5;"><b>{ai_prediction}</b></td></tr>
                            <tr><td style="padding: 8px; border-bottom: 1px solid #fca5a5;"><b>Trace ID:</b></td><td style="padding: 8px; border-bottom: 1px solid #fca5a5;"><code>{trace_id}</code></td></tr>
                        </table>
                        <p style="margin-top: 20px;"><i>Vui lòng truy cập AIOps Dashboard để kiểm tra chi tiết Trace này!</i></p>
                    </div>
                </body>
            </html>
            """
            
            await asyncio.to_thread(NotificationService._send_email_sync, subject, html_content)
            
        elif severity == "WARNING" or severity == "MEDIUM":
            pass