FROM python:3.13

ENV POETRY_VERSION=2.1

# Setup a spot for the api code
WORKDIR /usr/local/src/app/backend

RUN python -m pip install --upgrade pip && python -m pip install pipx && python -m pipx ensurepath && python -m pipx install "poetry==$POETRY_VERSION"

COPY poetry.lock .
COPY pyproject.toml .

# Project initialization:
RUN pipx run poetry config virtualenvs.create false \
  && pipx run poetry install --no-interaction --no-ansi --no-root

# RUN poetry run python app.py --generate-openapi-json ./api.json

# EXPOSE 8888

# Copy over the source code
COPY . .

# Run poetry install again, this time to install the root package
RUN pipx run poetry install --no-interaction --no-ansi

# # Configure Joplin-Nextcloud sync
# RUN npx joplin config sync.5.path https://nextcloud.jasport.org/remote.php/webdav/Joplin
# RUN npx joplin config sync.5.username ${NEXTCLOUD_USERNAME}
# RUN npx joplin config sync.5.password ${NEXTCLOUD_PASSWORD}
# RUN npx joplin config sync.target 5
# RUN npx joplin config api.token $JOPLIN_AUTH_TOKEN

# Kick things off
# ENTRYPOINT [ "poetry" ]
# CMD ["run", "python", "-m", "mydiary.api" ]
ENTRYPOINT [ "python" ]
CMD [ "-m",  "mydiary.api" ]