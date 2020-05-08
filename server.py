import asyncio
from asyncio import transports


class ClientProtocol(asyncio.Protocol):
    login: str
    server: 'Server'
    transport: transports.Transport

    def __init__(self, server: 'Server'):
        self.server = server
        self.login = None

    # Проверка логина на уникальность
    def check_login(self, login):
        for client in self.server.clients:
            if client.login == login:
                print("Клиент уже авторизирован")
                return False

        return True

    # Принять данные из сети
    def data_received(self, data: bytes):
        decoded_message = data.decode()
        if self.login is None:
            self.auth(decoded_message)
        else:
            if decoded_message.startswith("to:"):
                message_split = decoded_message.replace("to:", "").replace("\n", "").split(' ', 1)
                login = message_split[0]
                message = message_split[1]
                self.send_private_message(login, message)
            else:
                self.send_message(decoded_message)

    # Авторизация
    def auth(self, message):
        if not message.startswith("login:"):
            self.transport.write(f"Для участия в чате нужно авторизироваться!".encode())
            return

        login = message.replace("login:", "").replace("\n", "")

        if self.check_login(login):
            self.login = login
            self.transport.write(f"Привет, {self.login}!\n".encode())
            self.send_history(self.login)
        else:
            self.transport.write(f"Логин, {login} занят!\n".encode())
            self.transport.close()

    # Отправили сообщение в личку
    def send_private_message(self, login, message):
        format_string = f"<{self.login} (приватное)> {message}\n"
        encoded = format_string.encode()
        for client in self.server.clients:
            if client.login == login:
                client.transport.write(encoded)

    # Отправили сообщение в общий щат
    def send_message(self, message):
        format_string = f"<{self.login}> {message}"
        message_encoded = format_string.encode()

        # сохраняем в историю перед отправкой, чтобы даже если был только
        # чтобы история была, даже если был залогинен только 1 пользователь
        history_message = HistoryMessage(self.login, message)
        self.server.add_message(history_message)

        for client in self.server.clients:
            if client.login != self.login:
                client.transport.write(message_encoded)

    # Отправить историю пользователю который залогинился
    def send_history(self, login):
        message_list = self.server.get_history()
        for client in self.server.clients:
            if client.login == login:
                for message in message_list:
                    format_string = f"{message.login} написал: '{message.message}'\n"
                    message_encoded = format_string.encode()
                    client.transport.write(message_encoded)

    def connection_made(self, transport: transports.Transport):
        self.transport = transport
        self.server.clients.append(self)
        print("Соудинение установлено")

    def connection_lost(self, exc):
        self.server.clients.remove(self)
        print("Соудинение разорвано")


class Server:
    clients: list
    message_list: list

    def __init__(self):
        self.clients = []
        self.message_list = []

    def add_message(self, message):
        self.message_list.append(message)
        if len(self.message_list) > 10:
            self.message_list.pop(0)

    def get_history(self):
        return self.message_list

    def create_protocol(self):
        return ClientProtocol(self)

    async def start(self):
        loop = asyncio.get_running_loop()

        coroutine = await loop.create_server(
            self.create_protocol,
            "127.0.0.1",
            8888,
        )

        print("Сервер запущен...")

        await coroutine.serve_forever()


class HistoryMessage:
    login: str
    message: str

    def __init__(self, login, message):
        self.login = login
        self.message = message


process = Server()


try:
    asyncio.run(process.start())
except KeyboardInterrupt:
    print("Server Stop")
