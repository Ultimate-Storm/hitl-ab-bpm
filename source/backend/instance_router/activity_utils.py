import time
import pycamunda.processinst
import pycamunda.activityinst
import requests
import logging
from xml.etree import ElementTree

BASE_URL = 'http://camunda:8080/engine-rest'

def extract_cost_from_bpmn(path: str):
    ns = {'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
          'camunda': 'http://camunda.org/schema/1.0/bpmn'}
    # TODO remove hard-coding of concrete bpmn file
    root = ElementTree.parse(path).getroot()
    cost = {}

    for user_task in root.find('bpmn:process', ns).findall('bpmn:userTask', ns):
        ut_name = user_task.attrib['name']
        ut_cost_ext = user_task.find('bpmn:extensionElements', ns).find('camunda:properties', ns).findall(
            'camunda:property', ns)
        for ext_prop in ut_cost_ext:
            if ext_prop.attrib['name'] == 'cost':
                cost[ut_name] = int(ext_prop.attrib['value'])

    return cost


COST = extract_cost_from_bpmn('../resources/bpmn/helicopter_license/helicopter_vA.bpmn')

# time_elapsed = {'Schedule': 0,
#                 'Eligibility Test': 0,
#                 'Medical Exam': 0,
#                 'Theory Test': 0,
#                 'Practical Test': 0,
#                 'Approve': 0,
#                 'Reject': 0
#                 }

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)


def instance_terminated():
    """
    Rnsure all instances have terminated, instead of sleeping for 2 minutes
    In order to avoid an error and ensure the proper execution, it has be ensured that every instance has terminated
    before the data is retrieved.

    :return: True
    """
    instance_not_terminated = True
    while instance_not_terminated:
        get_instances = pycamunda.processinst.GetList(BASE_URL)
        instances = get_instances()
        # instance list is empty, all terminated, proceed
        if not instances:
            instance_not_terminated = False
        time.sleep(1)
    return True


def fetch_activity_duration():
    """
    get the duration of each task for all instances
    :return: a dict of time_elapsed of each task for all instances in one batch
    """
    time_elapsed = {}
    for key in COST.keys():
        time_elapsed[key] = 0
    activity_dict = {}
    time_start = time.time()
    instance_batch_list = []
    while True:
        get_instances = pycamunda.processinst.GetList(BASE_URL)
        instances = get_instances()
        for instance in instances:
            get_activity_instance = pycamunda.processinst.GetActivityInstance(BASE_URL, instance.id_)
            response = requests.get(get_activity_instance.url)
            if instance.id_ not in instance_batch_list:
                instance_batch_list.append(instance.id_)
            if 'childActivityInstances' in response.json():
                activity_name = response.json()['childActivityInstances'][0]['activityName']
                activity_id = response.json()['childActivityInstances'][0]['id']
                if not activity_dict.__contains__(activity_id):
                    time_start = time.time()
                    for value in activity_dict.values():
                        # print(value)
                        if value[0] is not None:
                            time_elapsed[value[0]] += value[1]
                activity_dict[activity_id] = [activity_name, time.time() - time_start]
                # print(activity_dict)
        time.sleep(0.1)
        if len(instances) == 0:
            logging.info('time_elapsed:')
            logging.info(time_elapsed)
            return time_elapsed


def cal_time_based_cost(batch_size, time_elapsed):
    """
    COST*batch_size/time_elapsed
    Offers an additional dimension to compare the variants. This also helps in terms of finding useful parameters for
    the human expert.
    :param batch_size:
    :return: dict of time based cost
    """
    cost_dict = COST.copy()
    for k, v in COST.items():
        if time_elapsed[k] != 0:
            cost_dict[k] = (cost_dict[k] * batch_size) / time_elapsed[k]
    logging.info('time_based_cost')
    logging.info(cost_dict)
    return cost_dict


def fetch_history_activity_duration(time_stamp):
    '''
    For debug use
    :param time_stamp:
    :return:
    '''
    time_query = 'finishedAfter=' + time_stamp
    history_url = '/history/activity-instance?'
    query_url = BASE_URL + history_url + time_query
    result = requests.get(query_url)
    dic = {}
    logging.info('fetch_history_activity_duration')
    logging.info(time_stamp)
    logging.info(result.json())
    for instance in result.json():
        dic[instance['id']] =[instance['activityName'], instance['durationInMillis']]
    logging.info(dic.values())
    return dic


def sumup_history_activity_duration(time_stamp):
    '''
    sum up dict of time elapsed for a batch of instances, values retrieved from history service
    :return: dict(time_elapsed)
    '''
    time_elapsed = {}
    for key in COST.keys():
        time_elapsed[key] = 0
    time_query = 'finishedAfter=' + time_stamp
    history_url = '/history/activity-instance?'
    query_url = BASE_URL + history_url + time_query
    activity_name_query = 'activityName='
    for key in time_elapsed.keys():
        result = requests.get(query_url + time_query + '&' + activity_name_query + key)
        for instance in result.json():
            time_elapsed[key] += instance['durationInMillis']
    logging.info('time_elapsed:')
    logging.info(time_elapsed)
    return time_elapsed

def get_format_timestamp():
    '''
    Formatted timestamps used for API calls
    By default, the date must have the format yyyy-MM-dd'T'HH:mm:ss.SSSZ, e.g., 2013-01-23T14:42:45.000+0200.
    Didn't find a way to express milliseconds, use .999 instead(deprecated)
    :return: formatted timestamp string
    '''
    return(time.strftime("%Y-%m-%dT%H:%M:%Smilliseconds%z", time.localtime()).replace('+', '%2b').replace('milliseconds', str(".%03d" %((time.time() - int(time.time())) * 1000))))