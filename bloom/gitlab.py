import requests


class GitlabException(Exception):
    def __init__(self, msg, code=None):
        if code:
            msg = "{msg}: {code}".format(**locals())
        super(GitlabException, self).__init__(msg)


class GitlabAuthException(GitlabException):
    def __init__(self, msg, code=None):
        super(GitlabAuthException, self).__init__(msg, code)


class Gitlab(object):
    def __init__(self, server, token=None):
        self.server = server
        self.token = token
        self.api_version = 4
        self.base_api_url = 'http://{server}/api/v{api_version}'.format(server=server, api_version=self.api_version)

    def update_params(self, params):
        if self.token:
            if params is None:
                params = {}
            params['private_token'] = self.token
        return params

    def api_get(self, query, params=None):
        r = requests.get(self.base_api_url + query, params=self.update_params(params))
        if r.status_code == 401:
            raise GitlabAuthException('Authentication Failed', r.status_code)
        elif r.status_code == 200:
            return r.json()
        else:
            raise GitlabException('Query {} failed.'.format(query), r.status_code)

    def api_post(self, query, params=None):
        r = requests.post(self.base_api_url + query, params=self.update_params(params))
        if r.status_code == 401:
            raise GitlabAuthException('Authentication Failed', r.status_code)
        elif r.status_code == 201:
            return r.json()
        else:
            raise GitlabException('Query {} failed.'.format(query), r.status_code)

    def auth(self):
        """ Authenticate by trying to get the projects """
        self.api_get('/projects')

    def get_repo(self, owner, repo):
        path = '{}/{}'.format(owner, repo)
        for repo_d in self.api_get('/projects', {'search': repo}):
            if repo_d.get('path_with_namespace', '') == path:
                return repo_d

    def list_branches(self, repo):
        res = self.api_get('/projects/{}/repository/branches'.format(repo['id']))
        return [d['name'] for d in res]

    def create_branch(self, repo, new_branch, base_branch):
        params = {'branch': new_branch, 'ref': base_branch}
        return self.api_post('/projects/{}/repository/branches'.format(repo['id']), params)

    def create_commit(self, repo, branch, commit_message, actions):
        params = {
            'branch': branch,
            'commit_message': commit_message,
            'actions': actions
        }
        return self.api_post('/projects/{}/repository/commits'.format(repo['id']), params)

    def update_file(self, repo, branch, commit_message, file_path, new_contents):
        actions = [{
                    'action': 'update',
                    'file_path': file_path,
                    'content': new_contents
                }
            ]
        return self.create_commit(repo, branch, commit_message, actions)    

    def create_pull_request(self, repo, source_branch, target_branch, title, body=''):
        params = {
            'source_branch': source_branch,
            'target_branch': target_branch,
            'title': title,
            'description': body
        }
        return self.api_post('/projects/{}/merge_requests'.format(repo['id']), params)

_gl = None

def get_gitlab_interface(server, quiet=False):
    global _gl
    if _gl is not None:
        return _gl

    config, oauth_config_path = get_bloom_config_and_path()
    if 'gitlab' in config:
        _gl = Gitlab(server, token=config['gitlab'])
        return _gl

    if quiet:
        return None

    info("")
    warning("Looks like bloom doesn't have a gitlab token for you yet.")
    warning("Go to http://{}/profile/personal_access_tokens to create one.".format(server))
    warning("Make sure you give it API access.")
    warning("The token will be stored in `~/.config/bloom`.")
    warning("You can delete the token from that file to have a new token generated.")
    warning("Guard this token like a password, because it allows someone/something to act on your behalf.")
    info("")
    if not maybe_continue('y', "Would you like to input a token now"):
        return None
    token = None
    while token is None:
        try:
            token = safe_input("Gitlab Token: ")
        except (KeyboardInterrupt, EOFError):
            return None
        try:
            gl = Gitlab(server, token=token)
            gl.auth()
            with open(oauth_config_path, 'w') as f:
                config.update({'gitlab': token})
                f.write(json.dumps(config))
            info("The token was stored in the bloom config file")
            _gl = gl
            break
        except GitlabAuthException:
            error("Failed to authenticate your token.")
            if not maybe_continue():
                return None

    return _gl        