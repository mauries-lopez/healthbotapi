# Healtbot API Documentation

This documentation provides information and resources for developing and deploying the Healthbot API. The healthbot API uses FastAPI and Firestore FastAPI.

## Table of Contents

- [Updating Fulfillment Response Parameters](#updating-fulfillment-response-parameters)
- [Deploying the FastAPI Application](#deploying-the-fastapi-application)
- [Dialogflow CX Webhook](#dialogflow-cx-webhook)
- [Integration to ASR](#integration-to-asr)
- [Sample Conversational Messages](#sample-conversational-messages)
- [Useful Links](#useful-links)

---

## Updating Fulfillment Response Parameters

Learn how to update fulfillment response parameters in Dialogflow CX:

- [BotFlo Tutorial: Updating Dialogflow CX Parameters from Webhook](https://botflo.com/updating-dialogflow-cx-parameters-from-webhook/)
- [Stack Overflow: Dialogflow CX Webhook for Fulfillment Using Node.js](https://stackoverflow.com/questions/64646879/dialogflow-cx-webhook-for-fulfilment-to-reply-user-using-nodejs)
- [Stack Overflow: Transition to Another Page from Dialogflow CX Webhook](https://stackoverflow.com/questions/68838654/dialogflow-cx-transition-to-another-page-from-webhook)
- [Dialogflow CX Fulfillment Concepts](https://cloud.google.com/dialogflow/cx/docs/concept/fulfillment)
- [Dialogflow Webhook JSON Reference](https://developers.google.com/assistant/df-asdk/reference/dialogflow-webhook-json)
- [Using Firestore FastAPI](https://github.com/anthcor/firestore-fastapi/tree/master/docs)

---

## Testing the FastAPI Application with Dialogflow CX

1. Run the FastAPI application using Uvicorn and reload with changes:
   ```
   uvicorn main:app --reload
   ```
2. Expose the application to the web using ngrok:
   ```
   ./ngrok http 8000
   ```
3. Copy the URL looking like: ```http://<url>.app.com``` and paste to webhooks on Dialogflow CX.
4. Go to Dialogflow CX and test the integration by using the webhook.


## Deploying the FastAPI Application
1. Navigate to project folder.
2. Build and submit the container to Google Cloud Container Registry:
   ```
   gcloud builds submit --tag gcr.io/ml-marcus-certification/health_bot_api
   ```
3. Deploy the containerized application to Google Cloud Run:
   ```
   gcloud run deploy --image gcr.io/ml-marcus-certification/health_bot_api --platform managed
   ```
Additional resources: 
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [Deploy Containerized Apps on Google Cloud Run](https://blog.somideolaoye.com/fastapi-deploy-containerized-apps-on-google-cloud-run)




## Dialogflow CX Webhook

Learn about the Dialogflow CX Webhook and response structure:

- [Dialogflow CX Webhook Response Reference](https://cloud.google.com/dialogflow/cx/docs/reference/rpc/google.cloud.dialogflow.cx.v3#webhookresponse)

---

## Sample Conversational Messages

Sample custom payload for a conversational interaction with the health bot:

```
{
  "quick_replies": [
    {
      "payload": "Yes",
      "content_type": "text",
      "title": "Yes"
    },
    {
      "payload": "No",
      "content_type": "text",
      "title": "No"
    }
  ],
  "text": "Good Day! I am Fil-Bis, a Nurse Bot. I will ask you some questions about your health. Is that okay?",
  "voice": "https://drive.google.com/uc?export=download&id=xxx"
}
```