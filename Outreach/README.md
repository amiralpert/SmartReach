# Outreach

Automated email campaigns and communication system.

## Features

- Email template management
- Campaign automation
- Contact list management  
- Personalized message generation
- Response tracking

## Components

### email_sender.py
Core email sending functionality with SMTP support.

### campaign_manager.py
Campaign orchestration and scheduling.

## Usage

```python
from email_sender import EmailSender

sender = EmailSender()
sender.send_campaign(template="intro", contacts=contact_list)
```