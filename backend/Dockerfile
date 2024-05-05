FROM python:3.10

ENV POETRY_VERSION=1.7

# Setup a spot for the api code
WORKDIR /usr/local/src/app/backend

RUN pip install --upgrade pip
RUN pip install "poetry==$POETRY_VERSION"

COPY poetry.lock .
COPY pyproject.toml .

# Project initialization:
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi --no-root

# RUN poetry run python app.py --generate-openapi-json ./api.json

# EXPOSE 8888

# https://stackoverflow.com/questions/36399848/install-node-in-dockerfile
# ENV NODE_VERSION=17.7.1
ENV NODE_VERSION=18.17.0
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

# Copy over the source code
COPY . .

# Run poetry install again, this time to install the root package
RUN poetry install --no-interaction --no-ansi

# Configure Joplin-Nextcloud sync
RUN npx joplin config sync.5.path https://nextcloud.jasport.org/remote.php/webdav/Joplin
RUN npx joplin config sync.5.username ${NEXTCLOUD_USERNAME}
RUN npx joplin config sync.5.password ${NEXTCLOUD_PASSWORD}
RUN npx joplin config sync.target 5
RUN npx joplin config api.token $JOPLIN_AUTH_TOKEN

# Kick things off
ENTRYPOINT [ "poetry" ]
CMD ["run", "python", "-m", "mydiary.api" ]
# CMD ["run", "python", "mydiary/api.py" ]