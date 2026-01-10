# Fitness Dashboard

React + TypeScript dashboard for visualizing running data from Strava and MapMyFitness.

## Setup

1. **Install dependencies:**
   ```sh
   npm install
   ```

2. **Configure environment variables:**
   Create a `.env` file in the `dashboard/` directory:
   ```env
   VITE_API_URL=http://localhost:8000
   VITE_IDENTITY_URL=http://localhost:8080
   VITE_OAUTH_CLIENT_ID=your_oauth_client_id
   ```

   - `VITE_API_URL`: Base URL of the fitness API
   - `VITE_IDENTITY_URL`: Base URL of the OAuth identity provider
   - `VITE_OAUTH_CLIENT_ID`: OAuth client ID (obtained from identity provider CLI)

3. **Register OAuth client:**
   Use the [identity provider](https://github.com/eswan18/identity) CLI to register this dashboard as a client, and then store the created CLIENT_ID in your `.env` file.

## Development

Run the development server:
```sh
npm run dev
```

The dashboard will be available at `http://localhost:5173`.

## Building

Build for production:
```sh
npm run build
```

Preview the production build:
```sh
npm run preview
```

## Code Quality

Format code with Prettier:
```sh
npm run format
```

Lint with ESLint:
```sh
npm run lint
```

## Authentication

The dashboard uses OAuth 2.0 Authorization Code flow with PKCE for authentication. When you first land on the page, you'll be redirected to the identity provider to log in. After authentication, you'll be redirected back with an authorization code that's exchanged for access tokens.

Tokens are stored in sessionStorage and automatically refreshed when they expire.
