FROM node:22-alpine
WORKDIR /srv
COPY package*.json ./
RUN npm ci
COPY . .
CMD ["npm", "start"]
