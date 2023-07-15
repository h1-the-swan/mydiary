# NOTE: This Dockerfile is only used in development. It provides a runtime
# environment where the JavaScript build process can run. In production the
# files built by this process are served from disk, while in development a HTTP
# server that's distributed with the UI build tools is used.
ARG VARIANT=18
FROM node:${VARIANT}

# Setup a spot for our code
WORKDIR /usr/local/src/app/mydiary-vuetify

# Install dependencies
# COPY package.json yarn.lock ./
COPY package.json ./
RUN npm install

# Copy in the source code
COPY . .

# RUN npx openapi-typescript-codegen --input ../backend/api.json --output ./src/api

# This tells build scripts and libraries that we're in development, so they
# can include stuff that's helpful for debugging even if it's a tad slower.
ARG NODE_ENV=development
ENV NODE_ENV $NODE_ENV

# Build the UI
# RUN yarn build

EXPOSE 3001

ENTRYPOINT [ "npm" ]
CMD [ "run", "generateAndStart" ]