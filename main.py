from flask import Flask, render_template, request
from requests import Session, get
from requests.exceptions import ConnectionError
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser
from time import sleep
from tqdm import tqdm
from local_settings import PASSWORD, USERNAME
import os


app = Flask(__name__)
API_URL = 'https://www.gokgs.com/json-cors/access'
PLAYERS = []
s = Session()
channelId = 0
letters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k',
           'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't']


def send(session, data):
    try:
        session.post(API_URL, json=data)
        req = session.get(API_URL)
        if req.status_code != 200:
            print(req.status_code, 'status')
            return -1
        return req.json()
    except ConnectionError:
        print('Connection erroe')
        return send(session, data)
    except Exception as e:
        print(e)
        quit()


def login(session):
    login_response = send(session, {
        'type': 'LOGIN',
        'name': USERNAME,
        'password': PASSWORD,
        'locale': 'en_US'
    })

    try:
        for message in login_response['messages']:
            if message['type'] == 'ROOM_NAMES':
                channelId = message['rooms'][0]['channelId']
                return channelId
    except:
        return login()


def logout(session):
    send(session, {
        'type': 'LOGOUT'
    })


class Player:
    place = ''
    username = ''
    rank = ''
    games = []

    def __init__(self):
        pass


class Game:
    white_player = {}
    black_player = {}
    timestamp = ''
    size, komi = 0, .0
    result = {}
    moves = []
    sgf = ''

    def __init__(self):
        pass

    def load(self, session, channelId):
        self.moves = []

        game_data = send(session, {
            'type': 'ROOM_LOAD_GAME',
            'timestamp': self.timestamp,
            'channelId': channelId
        })

        while game_data == -1:
            logout(session)
            channelId = login(session)
            game_data = send(session, {
                'type': 'ROOM_LOAD_GAME',
                'timestamp': self.timestamp,
                'channelId': channelId
            })

        for message in game_data['messages']:
            if message['type'] == 'GAME_JOIN':
                for step in message['sgfEvents']:
                    if step['type'] == 'PROP_GROUP_ADDED':
                        for prop in step['props']:
                            if 'loc' in prop.keys() and 'color' in prop.keys():
                                self.moves.append(prop)
                            elif prop['name'] == 'TIMELEFT':
                                self.moves.append(prop)
                break

        self.black_player = update_rank(self.black_player)
        self.white_player = update_rank(self.white_player)

        self.sgf = '(;'
        self.sgf += 'PB[' + self.black_player['name'] + ']'
        self.sgf += 'PW[' + self.white_player['name'] + ']'
        self.sgf += 'BR[' + self.black_player['rank'] + ']'
        self.sgf += 'WR[' + self.white_player['rank'] + ']'
        self.sgf += 'KM[' + str(self.komi) + ']'
        self.sgf += 'SZ[' + str(self.size) + '];'

        for move in self.moves:
            if 'loc' in move.keys():
                if move['loc'] != 'PASS':
                    if move['color'] == 'black':
                        self.sgf += 'B[' + letters[move['loc']['x']] + \
                            letters[move['loc']['y']] + '];'
                    else:
                        self.sgf += 'W[' + letters[move['loc']['x']] + \
                            letters[move['loc']['y']] + '];'
                else:
                    if move['color'] == 'black':
                        self.sgf += 'C[' + self.black_player['name'] + \
                            ' пропускает ход];'
                    else:
                        self.sgf += 'C[' + self.white_player['name'] + \
                            ' пропускает ход];'
            elif move['name'] == 'TIMELEFT':
                if move['color'] == 'black':
                    self.sgf += 'BL[' + str(int(move['float'])) + '];'
                else:
                    self.sgf += 'WL[' + str(int(move['float'])) + ' ];'

        self.sgf += ')'


def get_players():
    req = get('https://gokgs.com/top100.jsp')

    soup = BeautifulSoup(req.text, 'lxml')
    players = []

    for column in soup.body.table.tr:
        for _player in list(column.table.children)[1:]:
            player_data = list(_player.children)
            player = Player()
            player.place = player_data[0].text
            player.username = player_data[1].a.text
            player.rank = player_data[2].text
            players.append(player)

    return players


def update_games():
    global PLAYERS, channelId
    channelId = login(s)
    print('Loading players...')
    PLAYERS = get_players()
    print('Loading games...')
    i = 0
    while i < len(PLAYERS):
        archive = send(s, {
            'type': 'JOIN_ARCHIVE_REQUEST',
            'name': PLAYERS[i].username
        })

        while archive == -1:
            logout(s)
            channelId = login(s)
            archive = send(s, {
                'type': 'JOIN_ARCHIVE_REQUEST',
                'name': PLAYERS[i].username
            })

        PLAYERS[i].games = []
        for message in archive['messages']:
            if 'games' in message.keys():
                j = len(message['games']) - 1
                while j >= 0 and len(PLAYERS[i].games) < 2:
                    game_data = message['games'][j]
                    try:
                        if game_data['score'] != 'UNFINISHED' and (game_data['gameType'] in ['tournament', 'ranked', 'free', 'rengo']):
                            game = Game()
                            game.timestamp = game_data['timestamp']
                            game.result = game_data['score']
                            game.size = game_data['size']
                            game.score = game_data['score']
                            # game.duration = game_data['moveNum']
                            game.komi = game_data['komi']
                            game.white_player = game_data['players']['white']
                            game.black_player = game_data['players']['black']
                            PLAYERS[i].games.append(game)
                    except KeyError:
                        pass
                    j -= 1

        print('\r', i, 'out of', len(PLAYERS), end='')
        if len(PLAYERS[i].games) == 2:
            i += 1


def players_to_dict(players):
    data = []
    for p in players:
        games = []
        for i in range(2):
            is_rival_white = False
            rival = p.games[i].black_player
            if p.games[i].black_player['name'] == p.username:
                is_rival_white = True
                rival = p.games[i].white_player
            rival = update_rank(rival)

            time = parser.parse(p.games[i].timestamp)
            time = time.ctime()

            games.append({
                'number': i,
                'is_rival_white': is_rival_white,
                'timestamp': time,
                'rival': rival,
                'size': p.games[i].size,
                'score': p.games[i].score
                # 'duration': p.games[i].duration
            })

        data.append({
            'place': p.place,
            'username': p.username,
            'rank': p.rank,
            'games': games
        })
    return data


def update_rank(player):
    if not 'rank' in player.keys():
        player['rank'] = '?'
    return player


@ app.route('/')
def main():
    return render_template('index.html', players=players_to_dict(PLAYERS))


@ app.route('/viewer')
def viewer():
    username = request.args.get('player')
    game = int(request.args.get('game'))
    for p in PLAYERS:
        if p.username == username:
            while len(p.games[game].moves) == 0:
                p.games[game].load(s, channelId)
            return render_template('game_viewer.html', sgf=p.games[game].sgf)


if __name__ == '__main__':
    app.debug = True
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        update_games()
    app.run()
