import json
import requests
from teambition import Teambition
from json.decoder import JSONDecodeError


class TeamFlowy(object):
    def __init__(self):
        self.workflowy_url = 'https://workflowy.com/get_initialization_data?client_version=18'
        self.workflowy_login_url = 'https://workflowy.com/accounts/login/'
        self.headers = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                        'accept-encoding': 'gzip, deflate, br',
                        'accept-language': 'zh-CN,zh;q=0.8,en;q=0.6',
                        'cache-control': 'max-age=0',
                        'content-type': 'application/x-www-form-urlencoded',
                        'dnt': '1',
                        'origin': 'https://workflowy.com',
                        'referer': 'https://workflowy.com/accounts/login/',
                        'upgrade-insecure-requests': '1',
                        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'}
        self.workflowy_username = ''
        self.workflowy_password = ''
        self.tb_client_id = ''
        self.tb_client_secret = ''
        self.tb_access_token = ''
        self.tb_callback = ''
        self.session = None
        self.tb = None
        self.read_config()

    def read_config(self):
        with open('config.json', encoding='utf-8') as f:
            config = f.read()
            try:
                config_dict = json.loads(config)
            except JSONDecodeError:
                print('Config is invalid.')
                return

        workflowy_config = config_dict.get('Workflowy', {})
        self.workflowy_username = workflowy_config.get('username', '')
        self.workflowy_password = workflowy_config.get('password', '')

        teambition_config = config_dict.get('Teambition', {})
        self.tb_callback = teambition_config.get('callback', '')
        self.tb_client_id = teambition_config.get('client_id', '')
        self.tb_client_secret = teambition_config.get('client_secret', '')
        self.tb_access_token = teambition_config.get('access_token', '')

    def login_in_workflowy(self):
        print('login to workflowy...')
        if not self.session:
            self.session = requests.Session()
        self.session.post(self.workflowy_login_url,
                          data={'username': self.workflowy_username,
                                'password': self.workflowy_password,
                                'next': ''})
        return True

    def login_tb(self):
        print('login to teambition...')
        if self.tb_access_token:
            print('use the exists access token.')
            self.tb = Teambition(self.tb_client_id,
                                 self.tb_client_secret,
                                 access_token=self.tb_access_token)
            return True
        else:
            print('refetch the access token.')
            self.fetch_access_token()

    def fetch_access_token(self):
        self.tb = Teambition(self.tb_client_id,
                             self.tb_client_secret)
        authorize_url = self.tb.oauth.get_authorize_url('https://kingname.info')
        print(f'Please open this url: {authorize_url} in web browser and then copy the `code` and input below: \n')
        code = input('input the `code` here: ')
        fetch_result_dict = self.session.post('https://account.teambition.com/oauth2/access_token',
                                              data={'client_id': self.tb_client_id,
                                                    'client_secret': self.tb_client_secret,
                                                    'code': code,
                                                    'grant_type': 'code'}).json()
        self.tb_access_token = fetch_result_dict.get('access_token', '')
        if self.tb_access_token:
            self.login_tb()
            print(f'the latest access token is: {self.tb_access_token}\n update the config.')
            self.update_config()
            return True
        else:
            print('can not fetch the access token...')
            return False

    def update_config(self):
        config = {
            'Workflowy': {'username': self.workflowy_username,
                          'password': self.workflowy_password},
            'Teambition': {'client_id': self.tb_client_id,
                           'client_secret': self.tb_client_secret,
                           'access_token': self.tb_access_token,
                           'callback': self.tb_callback}}

        with open('config.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(config, indent=4))

    def get_outline(self):
        print('start to get the outline...')
        outlines_json = self.session.get(self.workflowy_url).text
        outlines_dict = json.loads(outlines_json)
        project_list = outlines_dict.get('projectTreeData', {})\
            .get('mainProjectTreeInfo', {})\
            .get('rootProjectChildren', [])
        task_dict = {}
        print('start to extract the task to be added...')
        self.extract_task(project_list, task_dict)
        print(f'the tasks to be added are: {task_dict}')
        return task_dict

    def extract_task(self, sections, task_dict, target_section=False):
        for section in sections:
            name = section['nm']
            if target_section:
                task_dict[name] = [x['nm'] for x in section.get('ch', [])]
                continue

            if name == '[Teambition]':
                target_section = True
            sub_sections = section.get('ch', [])
            self.extract_task(sub_sections, task_dict, target_section=target_section)

    def create_task(self, task_name, sub_task_list):
        tasklist = self.tb.tasklists.get(project_id='59d396ee1013d919f3348675')[0]
        tasklist_id = tasklist['_id']
        todo_stage_id = tasklist['stageIds'][0]
        task_info = self.tb.tasks.create(task_name, tasklist_id=tasklist_id, stage_id=todo_stage_id)
        if sub_task_list:
            task_id = task_info['_id']
            for sub_task_name in sub_task_list:
                self.tb.subtasks.create(sub_task_name, task_id=task_id)
        print(f'task: {task_name} with sub tasks: {sub_task_list} added.')

if __name__ == '__main__':
    team_flowy = TeamFlowy()
    if team_flowy.login_in_workflowy():
        task_dict = team_flowy.get_outline()
        print(task_dict)
        if team_flowy.login_tb():
            print('start to create tasks into teambition...')
            for task_name, sub_task_list in task_dict.items():
                team_flowy.create_task(task_name, sub_task_list)
