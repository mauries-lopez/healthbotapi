# allergies = ["pagkain", "gamot", "dust", "pollen", "balahibo ng hayop"]

def get_cx_id_of_flow(flow_display_name):
    request = dialogflowcx.types.flow.ListFlowsRequest()
    request.parent = agent_id
    client_flows = dialogflowcx.services.flows.FlowsClient()

    # Second param is flow ID for allergy-probing-flow

    print(f"Agent ID: {agent_id}", f"Flow to Search: {flow_display_name}")

    response_flows = client_flows.list_flows(request)

    for page in response_flows.pages:
        for flow in page.flows:
            if flow.display_name == flow_display_name:
                return flow.name
    return None

# Retrieving the ID of the page given its display name in DF CX
def get_cx_id_of_page(page_display_name, flow_id):
    request = dialogflowcx.types.page.ListPagesRequest()
    request.parent = flow_id
    client_pages = dialogflowcx.services.pages.PagesClient()
    # Second param is flow ID for allergy-probing-flow
    response_pages = client_pages.list_pages(request)

    for page in response_pages.pages:
        for cx_page in page.pages:
            if cx_page.display_name == page_display_name:
                return cx_page.name
    return None

# Moving to a page that is based on a condition
@app.post("/move_to_what_route")
async def change_route(request: Request):
    json_data = await request.json()
    print("WENT IN NEED TO CHECK 2")
    session_name = json_data['sessionInfo']['session']

    content = { 
            "fulfillment_response": {
                "messages": [
                    {
                    }
                ]
            },
            "session_info":{
                "session": session_name,
                "parameters":{
                }
            }
    }

    parameters = json_data['sessionInfo']['parameters']
    cur_allergy = parameters['cur-obj']
    lang_sess = parameters['lang-sess']
    hkb_module = db.collection(u'health_knowledge_base')
    allergy_doc = hkb_module.document('allergies')
    doc = allergy_doc.get()
    val = doc.to_dict()

    if lang_sess == 'tagalog' :
        allergy_list = 'allergy_var_fil'
    elif lang_sess == 'cebuano' :
        allergy_list = 'allergy_var_ceb'
    elif lang_sess == 'english' :
        allergy_list = 'allergy_var_en'

    # print(allergy_list)

    get_allergy_w_what = [val_aller[allergy_list] for val_aller in val['allergies_w_what']]
    allergy_flow_id = get_cx_id_of_flow('allergy-probing-flow')

    if cur_allergy in get_allergy_w_what : 
        print("It is there")
        index_val = get_allergy_w_what.index(cur_allergy)
        print(index_val)
        print(val['allergies_w_what'][index_val]['page_name'])
        content["target_page"] = get_cx_id_of_page(val['allergies_w_what'][index_val]['page_name'], allergy_flow_id)
        print(content["target_page"])
    else :
        print("Not in there")
        content["target_page"] = get_cx_id_of_page('side-effects-duration-relief-follow-up', allergy_flow_id)

    print(content)
    return JSONResponse(content, status_code=200)

@app.post('/store_flagging_values')
async def store_flagging_values(request: Request):
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

    # Save Flags required for Physical Flagging
    if parameters.get('physical_flags') is None:
        flags = {'number': []}
    else:
        flags = parameters['physical_flags']

    flag_list = set(db.collection('health_knowledge_base').document('parameter_list').get().to_dict()['physical_flags'])

    for index, key, in enumerate(parameters):
        if key in flag_list:
            if parameters['module'] is 'head_module':
                flags[key.replace('x', parameters['cur-obj'])] = parameters[key]
            else:
                flags[key] = parameters[key]
    
 
    content['session_info']['parameters']['physical_flags'] = flags

    return JSONResponse(content, status_code=200)

@app.get('/test')
async def test(request: Request):
    return JSONResponse(content={'message' : 'HAHA'}, status_code=200)
