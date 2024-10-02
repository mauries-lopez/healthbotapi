from typing import Any, Dict
import os
import json
from fastapi import Body, Request, FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from google.cloud import firestore
from google.cloud import dialogflowcx_v3 as dialogflowcx
import pytz
from datetime import datetime
# from reportgenerator import Report

from dotenv import load_dotenv

load_dotenv()
agent_id = os.getenv('AGENT_ID')
project_id = os.getenv('PROJECT_ID')
##location = os.getenv('LOCATION')

# * Set the model config file
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="config/credentials.json"

app = FastAPI()
db = firestore.Client()

# Object for compiling all the findings
class confirmFindings:
    def __init__(self, finding, value):
        self.finding = finding
        self.value = value

    def __str__(self):
        return f"{self.finding}: {self.value}"
    
    def to_dict(self):
        return {
            'finding': self.finding,
            'value': self.value
        }

compileFindings = []

# * The Response Module of the health bot
@app.post("/return_custom_payload")
async def return_custom_payload(request: Request):
    # Session Variables
    json_data = await request.json()
    session_name = json_data['sessionInfo']['session']
    
    parameters = json_data['sessionInfo']['parameters']
    lang_sess = parameters['lang-sess']
    collection_name = parameters['module']
    custom_response_key = parameters['custom_response_key']

    doc_ref = None
    existing = False

    if 'cur-obj' in parameters.keys():
        if parameters['cur-obj'] != 'END' and parameters['cur-obj'] != None:
            current_object = parameters['cur-obj']
            doc_ref = db.collection(collection_name).document(custom_response_key+'-'+current_object).get()
            if doc_ref.exists:
                existing = True
    
    if not existing: 
        doc_ref = db.collection(collection_name).document(custom_response_key).get()

    val = doc_ref.to_dict()

    # Build Quick Reply Payload
    payload, qck_replies = {}, []
    try :
        if val != None and lang_sess != None:
            print('Chatbot Responded: ', val['question_translation'][lang_sess+'_response'], '|', val['qck_reply'][lang_sess+'_replies'])
            for qc_rep in val['qck_reply'][lang_sess+'_replies'] : 
                rep_pyl = {"payload" : qc_rep, "content_type" : "text", "title" : qc_rep}
                if qck_replies != None:
                    qck_replies.append(rep_pyl)
    except :
        print('Chatbot Responded: ', val['question_translation'][lang_sess+'_response'], '|', '---')
        pass

    if len(qck_replies) > 0: 
        payload['quick_replies'] = qck_replies
    try :
        if val != None and lang_sess != None:
            payload['text'] = val['question_translation'][lang_sess+'_response']
            payload['voice'] = val['voice_link'][lang_sess+'_audio']
    except :
        # ? This might be unused
        if val != None and lang_sess != None:
            payload['text'] = val['question'][lang_sess+'_response']
    try :
        if lang_sess != None:
            payload['language'] = lang_sess
    except :
        pass

    # Build Custom Payload
    content = {'fulfillment_response': {}}
    content['fulfillment_response']['messages'] = [{'payload' : payload}]
    content['session_info'] = {"session": session_name}

    return JSONResponse(content=content, status_code=200)

# * Get the next object in the list based on a current and the next object
def get_next_obj(cur_obj, next_obj, prefix_arr, db_doc_nm):
    # Fetch Object List
    hkb_module = db.collection(u'health_knowledge_base')
    db_doc = hkb_module.document(db_doc_nm)
    doc = db_doc.get()
    val = doc.to_dict()
    gen_list = val[prefix_arr+'_objects']

    # Set Object
    if not cur_obj and not next_obj :
        cur_obj = gen_list[0]
        next_obj = gen_list[1]
    elif next_obj == 'END' :
        cur_obj = 'END'
    else :
        # ? This might be unused
        index_allergy = gen_list.index(next_obj)
        cur_obj = gen_list[index_allergy]
        try :
            next_obj = gen_list[index_allergy+1]
        except :
            next_obj = 'END'

    print('Current Object: ', cur_obj, '|', 'Next Object: ', next_obj)

    return cur_obj, next_obj

# * Routing and checking if the flow is going to end
@app.post("/change_object_route")
async def change_object_route(request: Request):
    # Session Variables
    json_data = await request.json()
    session_name = json_data['sessionInfo']['session']
    content = { 
        "fulfillment_response": {
            "messages": [{}]
        },
        "session_info":{
            "session": session_name,
            "parameters":{}
        }
    }
    try :
        parameters = json_data['sessionInfo']['parameters']
    except :
        parameters = {}


    prefix_arr = parameters['prefix-arr']
    db_doc_nm = parameters['db_doc_nm']

    try :
        cur_obj = parameters['cur-obj']
        next_obj = parameters['next-obj']
    except :
        cur_obj = ''
        next_obj = ''

    # Set Object Loop
    cur_obj, next_obj = get_next_obj(cur_obj, next_obj, prefix_arr, db_doc_nm)
    if next_obj == 'END' and cur_obj == 'END' :
        content['session_info']['parameters']['cont-obj-flag'] = "FALSE"
        content['session_info']['parameters']['cur-obj'] = None
        content['session_info']['parameters']['next-obj'] = None
    else :
        content['session_info']['parameters']['cont-obj-flag'] = "TRUE"
        content['session_info']['parameters']['cur-obj'] = cur_obj
        content['session_info']['parameters']['next-obj'] = next_obj

    return JSONResponse(content, status_code=200)

# * Store medical data to knowledge base
def store_medical_history(page_flow, parameters, params_to_store, username, session_name) :
    print(f'Storing Medical Information of {username}')

    ph_timezone = pytz.timezone("Asia/Hong_Kong")
    ts = datetime.now(ph_timezone)
    # print(ts)

    # Session variables
    med_history_doc = {}
    med_history_doc['module'] = page_flow
    med_history_doc['session_name'] = session_name
    med_history_doc['created_at'] = ts
    med_history_doc['updated_at'] = ts

    # Save session variables based on defined parameter list for the current module 
    # ex. (firestore/health_knowledge_base/parameter_list/{Current Module Name})
    ignored = []
    unavailable = []
    for key, value in parameters.items():
        try :
            if key in params_to_store and value is not None:
                med_history_doc[key] = value
            else :
                ignored.append(key)
        except :
            unavailable.append(key)

    print('Ignored: ', ignored)
    print('Unavailable: ', unavailable)

    # Save to Firestore
    doc_id = f"med_rec_{med_history_doc['module']}_{ts.strftime('(%Y-%m-%d)-%H:%M:%S:%f')[:-3]}"
    doc_ref = db.collection(u'children_health_data').document(username).collection('medical_history').document(doc_id).set(med_history_doc)
    print(doc_ref)
    print("Successfully Appended Session Details to Firestore")

# * Reset certain parameters based on a list from the knowledge base
@app.post("/reset_vals")
async def reset_vals(request: Request):
    # Session Variables
    json_data = await request.json()
    session_name = json_data['sessionInfo']['session']
    parameters = json_data['sessionInfo']['parameters']
    content = { 
        "fulfillment_response": {
            "messages": [{}]
        },
        "session_info":{
            "session": session_name,
            "parameters": {}
        }
    }

    print("Resetting Session Variables")

    # Fetch Parameter List (to remove)
    hkb_module = db.collection(u'health_knowledge_base')
    parameters_list = hkb_module.document('parameter_list')
    doc = parameters_list.get()
    val = doc.to_dict()
    collection_name = parameters['module']
    to_none_parameters = val[collection_name]
    
    # Reset Variables
    resets = []
    for key in to_none_parameters:
        try :
            if key != 'cur-obj' :
                content['session_info']['parameters'][key] = None
                resets.push(key)
        except :
            pass
    
    print('Resets: ', resets)

    return JSONResponse(content, status_code=200)

# * Get certain parameters based on a list from the knowledge base and store to knowledge base
@app.post("/get_n_store")
async def get_session_value(request: Request):
    json_data = await request.json()
    session_name = json_data['sessionInfo']['session']
    parameters = json_data['sessionInfo']['parameters']

    content = { 
        "fulfillment_response": {
            "messages": [{}   ]
        },
        "session_info":{
            "session": session_name,
            "parameters":{}
        }
    }

    hkb_module = db.collection(u'health_knowledge_base')
    parameters_list = hkb_module.document('parameter_list')
    doc = parameters_list.get()
    val = doc.to_dict()

    # print(parameters)
    collection_name = parameters['module']
    params_to_store = val[collection_name]
    username = parameters['school'] + '-' + parameters['student-id']

    store_medical_history(collection_name, parameters, params_to_store, username, session_name)

    return JSONResponse(content, status_code=200)

# * Mental Health
# * Compute for the mental health flagging scores
def compute_mh_flag_score(parameters):
    # at - Attention, in - Internalizing, ex - Externalizing, ot - Others missing - Empty Answers
    at_ss_flag, in_ss_flag, ex_ss_flag, other_ss_flag, answers = 0, 0, 0, 0, 0  
    at_keys = ['is-restless', 'is-overactive', 'is-daydreaming', 'easily-distracted', 'has-difficulty-to-focus']
    in_keys = ['feels-sad-or-unhappy', 'feels-hopeless', 'has-no-self-confidence', 'feels-anxious', 'lacks-excitement-in-life']
    ex_keys = ['fights-kids', 'does-not-follow-rules-or-advices', 'is-not-empathic', 'hurts-others', 'blames-others-for-self-misfortunes', 'steals-things', 'is-selfish']
    ot_keys = ['feels-body-pain', 'spends-more-time-alone', 'easily-gets-tired', 'has-problems-with-teachers', 'is-not-interested-in-learning', 'fearful-for-uncertainty', 'is-quick-to-be-angry-and-irritated', 'lacks-interest-in-making-friends', 'absents-in-class', 'gets-lower-grades', 'doctor-finds-nothing-wrong', 'has-difficulty-sleeping', 'has-separation-anxiety', 'not-a-good-person', 'does-careless-actions', 'gets-hurt-frequently', 'does-actions-not-according-to-age', 'is-emotionless']

    # Scoring Weights
    weights = {"often": 2, "sometimes": 1, "never": 0, "return": 0}

    # Compute Mental Health Scores
    print('Computing Mental Flags')
    for index, key in enumerate(parameters):
        if parameters[key] == 'return' or parameters[key] == None:
            continue

        if key in at_keys:
            at_ss_flag += weights[parameters[key]]
            answers += 1

        elif key in in_keys:
            in_ss_flag += weights[parameters[key]]
            answers += 1

        elif key in ex_keys:
            ex_ss_flag += weights[parameters[key]]
            answers += 1

        elif key in ot_keys:
            other_ss_flag += weights[parameters[key]]
            answers += 1

    return at_ss_flag, in_ss_flag, ex_ss_flag, other_ss_flag, sum([at_ss_flag, in_ss_flag, ex_ss_flag, other_ss_flag]), answers

@app.post("/mental_health_flagging")
async def mental_health_flagging(request: Request):
    json_data = await request.json()

    session_name = json_data['sessionInfo']['session']
    parameters = json_data['sessionInfo']['parameters']
    content = { 
        "fulfillment_response": {
            "messages": [{}]
        },
        "session_info":{
            "session": session_name,
            "parameters": {}
        }
    }

    # Compute Mental Health Scores
    at_flag, in_flag, ex_flag, _, total, answers = compute_mh_flag_score(parameters)
    content['session_info']['parameters']['has_attention_impairment'] = "Yes" if at_flag >= 7 else "No"
    content['session_info']['parameters']['has_internalizing_impairment'] = "Yes" if in_flag >= 5 else "No"
    content['session_info']['parameters']['has_externalizing_impairment'] = "Yes" if ex_flag >= 7 else "No"
    content['session_info']['parameters']['has_psychological_impairment'] = "Yes" if total >= 28 else "No"
    content['session_info']['parameters']['attention_impairment_score'] = at_flag
    content['session_info']['parameters']['internalizing_impairment_score'] = in_flag
    content['session_info']['parameters']['externalizing_impairment_score'] = ex_flag
    content['session_info']['parameters']['psychological_impairment_score'] = total

    # Invalid Questionaire
    content['session_info']['parameters']['invalid_questionnaire'] = "Yes" if answers <= 31 else "No"
    content['session_info']['parameters']['total_answers'] = answers

    return JSONResponse(content, status_code=200)

# * Physical Health
# * Compute for the physical health flagging scores
def compute_ph_flag_score(parameters):
    yes_no_keys = ['fever-is-on-off','has-experienced-extremeheadache','has-any-form-of-discharge','discharge-hasfoulsmell','had-inserted-object-into-ear','has-pain','has-loss-of-sight','stomach-flu-had-chills','stomach-flu-experienced-dehydration','stomach-flu-food-had-different-smell-or-taste','stomach-flu-experienced-vomitting','rushed-to-hospital','had-blindness','had-experienced-dizziness','had-vomitted','had-passed-out','head-x-confirmation','is-recurring','ache-x-confirmation','heart-lungs-x-confirmation','experienced-shortness-of-breath','hospitalized-due-to-heart-related-issues','mtth-x-confirmation','had-difficult-time-chewing','has-pain-in-the-nose','nosepain-is-recurring','had-insertedobject-into-nose','has-experienced-pain-while-urinating','eyep-x-confirmation','earp-x-confirmation']
    count_keys = ['stomach-flu-vomit-count', 'bowel-times-a-day', 'stomach-flu-boweltimes']
    pain_scale_keys = ['stomach-flu-painintensity', 'pain-intensity', 'swelling-painintensity', 'menstrual-pain-intensity', 'stomach-flu-painintensity', 'urine-pain-intensity', 'discomfortability', 'pain-intensity-due-to-inserted-object']
    temperature_keys = ['current-temperature', 'highest-temperature']
    
    time_keys = ['duration', 'duration-of-object-in-nose', 'duration-of-nose-pain']
    time_weights = {'7 hours': 1, '8 hours': 2, '1 day': 3, '3 days': 4, '1 week': 5, '2 weeks': 6}

    choice_effect_keys = ['side-effects']
    choice_color_keys = ['phlegm-color', 'spit-appearance', 'poop-color', 'frequent-urine-color']

    print('Computing Physical Flags')
    for index, key in enumerate(parameters):
        if key in yes_no_keys:
            try:
                if parameters['cur-obj'] != 'fungal-infection':
                    if parameters['cur-obj'] != 'injury':
                        if (parameters[key] in ['meron', 'minsan']):
                            return 1
                    
            except:
                if (parameters[key] in ['meron', 'minsan']):
                    return 1

        if key in count_keys:
            try:
                if key == 'stomach-flu-vomit-count' and 3 <= parameters[key]:
                    return 1
                elif 4 <= parameters[key]:
                    return 1
            except:
                pass

        if key in pain_scale_keys:
            try:
                if 8 <= int(parameters[key]):
                    return 1
            except:
                pass
            
        if key in temperature_keys:
            try:
                if 39.5 <= float(parameters[key]):
                    return 1
            except:
                pass
        
        if key in time_keys:
            try:
                if key == 'duration':
                    if parameters['module'] == 'buto_and_muscle_module' and time_weights['3 days'] <= time_weights[parameters[key]]:
                        return 1
                    if parameters['module'] == 'cough_and_cold_module' and time_weights['2 weeks'] <= time_weights[parameters[key]]:
                        return 1                        
                    if parameters['module'] == 'heart_lungs_module' and time_weights['1 week'] <= time_weights[parameters[key]]:
                        return 1
                else:
                    if key == 'duration-of-object-in-nose' and time_weights['1 day'] <= time_weights[parameters[key]]:
                        print('FLAGGING', key)
                        return 1
                    
                    if time_weights['3 days'] <= time_weights[parameters[key]]:
                        print('FLAGGING', key)
                        return 1
            except: 
                pass

        # if key in choice_effect_keys and parameters['module'] == 'allergy_module':
        #     for effect in parameters[key]:
        #         if effect in ['nausea and vomiting', 'difficulty breathing']:
        #             return 1
        
        if key in choice_effect_keys:
            if parameters['module'] == 'allergy_module':
                if parameters[key] in ['nausea and vomiting', 'difficulty breathing', 'rashes']:
                    return 1
                
        if key in choice_color_keys:
            if parameters['module'] == 'gu_module':
                if parameters[key] in ['brownish', 'bloody red']:
                    return 1                
            if parameters[key] in ['black', 'red', 'brown']:
                return 1                
    return 0

@app.post("/physical_health_flagging")
async def physical_wellness_flagging(request: Request):
    json_data = await request.json()

    session_name = json_data['sessionInfo']['session']
    parameters = json_data['sessionInfo']['parameters']
    content = { 
        "fulfillment_response": {
            "messages": [{}]
        },
        "session_info":{
            "session": session_name,
            "parameters": {}
        }
    }

    # Compute Physical Health Scores
    emergency = compute_ph_flag_score(parameters)
    content['session_info']['parameters']['total_emergency_flag_score'] = emergency
    
    return JSONResponse(content=content, status_code=200)

# Ginagamit ito para lahat nung mga sagot ng user ay mastore sa "local" or sa isang object muna then kapag nacompile na lahat ng sagot -> isang bagsakan nalang ang save sa database using /save_local_findings
@app.post("/local_store_findings")
async def local_store_findings(request: Request):
    print("Test local store findings endpoint")

    json_data = await request.json()
    session_name = json_data['sessionInfo']['session']
    parameters = json_data['sessionInfo']['parameters']

    content = { 
        "fulfillment_response": {
            "messages": [{}   ]
        },
        "session_info":{
            "session": session_name,
            "parameters":{}
        }
    }

    hkb_module = db.collection(u'health_knowledge_base')
    parameters_list = hkb_module.document('parameter_list')
    doc = parameters_list.get()
    val = doc.to_dict()
    collection_name = parameters['module']
    params_to_store = val[collection_name]

    # store_medical_history(collection_name, parameters, params_to_store, username, session_name)
    for i in range(len(params_to_store)):
        # print(params_to_store[i], parameters[params_to_store[i]])
        # print(params_to_store[i])
        # print(parameters[params_to_store[i]])
        finding = params_to_store[i]
        value = parameters[params_to_store[i]]
        compileFindings.append(confirmFindings(finding, value))

    return JSONResponse(content, status_code=200)

@app.post("/save_findings")
async def save_findings(request: Request):

    json_data = await request.json()
    parameters = json_data['sessionInfo']['parameters']
    collection_name = parameters['module']     
    username = parameters['school'] + '-' + parameters['student-id']
    session_name = json_data['sessionInfo']['session']

    ph_timezone = pytz.timezone("Asia/Hong_Kong")
    ts = datetime.now(ph_timezone)

    serialized_findings = [finding.to_dict() for finding in compileFindings]

    # Session variables
    med_history_doc = {
        'module': collection_name,
        'session_name': session_name,
        'created_at': ts,
        'updated_at': ts,
        'compiled_findings': {}
    }

    # Process each finding and ensure unique keys
    for finding in serialized_findings:
        key = finding['finding']
        value = finding['value']

        # Ensure unique field name by appending an index if the key already exists
        unique_key = key
        counter = 1
        while unique_key in med_history_doc['compiled_findings']:
            unique_key = f"{key}_{counter}"
            counter += 1

        med_history_doc['compiled_findings'][unique_key] = value

    doc_id = f"med_rec_{med_history_doc['module']}_compiled_{ts.strftime('(%Y-%m-%d)-%H:%M:%S:%f')[:-3]}"
    db.collection(u'children_health_data').document(username).collection('medical_history').document(doc_id).set(med_history_doc)
    print("Successfully Appended Session Details to Firestore")
    
    #Reset compileFindings to prepare for the next diagnosis
    compileFindings.clear()

    return JSONResponse(content={'message' : 'OK'}, status_code=200)

# * Test
@app.post("/test_endpoint")
async def test_endpoint(request: Request):
    print("Testing the endpoint")
    return JSONResponse(content={'message' : 'OK'}, status_code=200)

@app.post("/set_response")
async def set_response(request: Request):
    # Session Variables
    json_data = await request.json()
    session_name = json_data['sessionInfo']['session']
    parameters = json_data['sessionInfo']['parameters']
    lang_sess = parameters['lang-sess']
    collection_name = parameters['module']

    custom_response_collection = parameters['custom_response_collection']
    custom_response = parameters['set_response']

    doc_ref = None

    #buto_and_muscle_module -> bm_response
    doc_ref = db.collection(collection_name).document(custom_response_collection).get()

    #All values inside bm_response
    val = doc_ref.to_dict()

    #"Hello"
    #val[lang_sess][custom_response] 


    # Build Quick Reply Payload
    payload, qck_replies = {}, []
    try :
        if val != None and lang_sess != None:
            payload['text'] = val[lang_sess][custom_response]
            for qc_rep in val['qck_reply'][lang_sess+'_replies'] : 
                rep_pyl = {"payload" : qc_rep, "content_type" : "text", "title" : qc_rep}
                if qck_replies != None:
                    qck_replies.append(rep_pyl)
    except:
        pass

    if len(qck_replies) > 0: 
        payload['quick_replies'] = qck_replies
    try :
        if lang_sess != None:
            payload['language'] = lang_sess
    except :
        pass

    # Build Custom Payload
    content = {'fulfillment_response': {}}
    content['fulfillment_response']['messages'] = [{'payload' : payload}]
    content['session_info'] = {"session": session_name}

    return JSONResponse(content=content, status_code=200)

@app.post("/mobile_download_modules")
def firestoreToJson():
    try:
        collections = db.collections()
        print("hello")
        data = {}
        for collection in collections:
            if collection.id != 'children_health_data':
                docs = collection.stream()
                data[collection.id] = {}
                for doc in docs:
                    data[collection.id][doc.id] = doc.to_dict()
                    #check if key voice_link exists
                    if 'voice_link' in data[collection.id][doc.id].keys():
                        data[collection.id][doc.id].pop('voice_link')
        print(data['mobile_routes'])
        return JSONResponse(content=data, status_code=200)
    except Exception as error:
        print(error)
        return JSONResponse(content={'message' : 'Error'}, status_code=500)

@app.post("/mobile_upload_modules")
async def jsonToFirestore(request: Request):
    data = await request.json()

    try:
        username = data["childID"]
        doc_id = data["recordID"]
        objectName = data["object"]

        del data['recordID']
        del data['childID']
        del data['object']

        if data['module'] == 'mental_health_module':
            at_flag, in_flag, ex_flag, _, total, answers = compute_mh_flag_score(data)
            data['has_attention_impairment'] = "Yes" if at_flag >= 7 else "No"
            data['has_internalizing_impairment'] = "Yes" if in_flag >= 5 else "No"
            data['has_externalizing_impairment'] = "Yes" if ex_flag >= 7 else "No"
            data['has_psychological_impairment'] = "Yes" if total >= 28 else "No"
            data['attention_impairment_score'] = at_flag
            data['internalizing_impairment_score'] = in_flag
            data['externalizing_impairment_score'] = ex_flag
            data['psychological_impairment_score'] = total
            data['invalid_questionnaire'] = "Yes" if answers <= 31 else "No"
            data['total_answers'] = answers

    # get from firestore mobile_routes
        moduleRouteDoc = db.collection(u'mobile_routes').document(data['module']).get().to_dict()

        # check if moduleRouteDoc['object_type'] exists
        if 'object_type' in moduleRouteDoc.keys():
            objKey = moduleRouteDoc['object_type']['key']
            obj = moduleRouteDoc['object_type'][objectName]

            data[objKey] = obj

        db.collection(u'children_health_data').document(username).collection('medical_history').document(doc_id).set(data)
        
    except Exception as error:
        # print error
        print(error)

        return JSONResponse(content={'message' : 'Error'}, status_code=500)

    return JSONResponse(content={'message' : 'Ok'}, status_code=200)