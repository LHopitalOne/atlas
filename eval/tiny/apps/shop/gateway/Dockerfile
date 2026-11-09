FROM node:20-alpine
WORKDIR /srv
COPY package*.json ./
RUN npm install --omit=dev
COPY src ./src
ENV GATEWAY_HOST=0.0.0.0
CMD ["node", "src/server.js"]
