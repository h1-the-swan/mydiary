FROM python:3.8

# Setup a spot for the api code
WORKDIR /usr/local/src/app/backend

COPY poetry.lock .
COPY pyproject.toml .

RUN pip install poetry

# Copy over the source code
COPY . .

# Project initialization:
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

# RUN poetry run python app.py --generate-openapi-json ./api.json

# EXPOSE 8888

# https://stackoverflow.com/questions/36399848/install-node-in-dockerfile
ENV NODE_VERSION=17.7.1
# RUN apt install -y curl
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash
ENV NVM_DIR=/root/.nvm
RUN . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm use v${NODE_VERSION}
RUN . "$NVM_DIR/nvm.sh" && nvm alias default v${NODE_VERSION}
ENV PATH="/root/.nvm/versions/node/v${NODE_VERSION}/bin/:${PATH}"
RUN node --version
RUN npm --version

RUN npm install joplin
RUN npx joplin config sync.5.path http://192.168.0.111:48916/remote.php/webdav/Joplin
RUN npx joplin config sync.5.username admin
RUN npx joplin config sync.5.password password
RUN npx joplin config sync.target 5
RUN npx joplin config api.token $JOPLIN_AUTH_TOKEN

# Kick things off
ENTRYPOINT [ "poetry" ]
CMD ["run", "python", "-m", "mydiary.api" ]
# CMD ["run", "python", "mydiary/api.py" ]