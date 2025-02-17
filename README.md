## WhatsApp Chatbot con Flask, Twilio, OpenAI y Odoo

- **Paquetes:**

  ```python 
  pip install -r requirements.txt
  ````

  
## Descripción

Este proyecto es una aplicación desarrollada en Flask que actúa como un chatbot para interactuar con posibles clientes a través de WhatsApp utilizando Twilio y OpenAI. El chatbot asiste a los clientes, ofrece servicios, propone presupuestos, descuentos y ofertas, y finalmente, recopila el nombre y correo electrónico del cliente para crear un contacto en Odoo, generar un lead en el CRM y enviar un presupuesto al cliente.

## Características

- **Integración con WhatsApp y Twilio**: La aplicación permite enviar y recibir mensajes de WhatsApp utilizando Twilio como proveedor de servicios de mensajería.
- **IA Potenciada por OpenAI**: El chatbot utiliza OpenAI para generar respuestas contextuales, ofrecer servicios, proponer presupuestos, y personalizar la experiencia del cliente.
- **Generación de Leads y Presupuestos en Odoo**: Los datos de contacto recopilados se utilizan para crear un lead en el CRM de Odoo, y automáticamente se genera y envía un presupuesto al cliente.
- **Personalización de Ofertas**: El chatbot propone ofertas y descuentos basados en la conversación con el cliente, mejorando la tasa de conversión.
- **Automatización del Proceso de Ventas**: Desde la primera interacción hasta el envío del presupuesto, todo el proceso está automatizado para una experiencia de usuario eficiente y sin fricciones.

## Diagrama

![App Screenshot](https://back.jumotech.com/uploads/Whatsapp_Chatbot_012565b233.png)

## Endpoint

### `POST /whatsapp`
