# Sign in with Google

An API key cannot authorise edits to a private Google Doc. CiteGoblin uses desktop OAuth: Google opens in your browser, you choose your account and approve access, and CiteGoblin saves the authorisation for later runs. Google passwords never pass through CiteGoblin.

**CGPS users:** obtain CiteGoblin's desktop OAuth client JSON privately from the maintainer, then run the login command below. You do not need to create your own Google Cloud project. The registered application currently accepts CGPS accounts only. No credentials or user tokens are included in this public repository.

**Maintainers or self-hosted installations:** application registration is a one-time step:

1. Create a Google Cloud project and enable **Google Docs API** and **Google Drive API**.
2. Configure the OAuth consent screen for CiteGoblin. Use your organisation's internal app if appropriate, or add authorised test users while developing an external app.
3. Create an OAuth client with application type **Desktop app**, then download its JSON configuration. This is an OAuth client configuration, not an API key or a service-account key.
4. Run:

```sh
citegoblin login --client-secrets /path/to/downloaded-client.json
```

The browser opens Google's account chooser and consent page. Authorise using the account that has editing and commenting access to the document. The callback returns to a temporary local listener on `127.0.0.1`; no public server, browser automation or copied verification code is required.

Once a desktop client is configured, the first `run`, `init` or `apply` automatically opens sign-in in an interactive terminal if no usable authorisation exists. Later runs reuse it and refresh expired access tokens automatically. Revoked permissions trigger sign-in again; temporary network failures produce an error without needlessly starting a new login. Non-interactive runs never start a browser: run `login` once in a terminal first.

The OAuth client is configured once per installation. For a distributed release, the maintainer can supply a registered desktop client configuration so each user only needs to sign in. A public client configuration is not a user's token; never distribute access tokens, refresh tokens or service-account keys. Google consent/publishing and organisation policies still apply. See [Google's desktop OAuth guide](https://developers.google.com/identity/protocols/oauth2/native-app).

## Saved authorisation

Tokens are stored in the operating system's keychain by default: macOS Keychain, Windows Credential Manager or a supported Linux secret store. Plaintext fallback is never automatic. If no supported keychain is available, explicitly choose private file storage:

```sh
citegoblin login --client-secrets /path/to/downloaded-client.json --token-file /private/path/token.json
```

That choice is remembered locally. On POSIX systems the token file is written with owner-only permissions. Do not share or commit it. `CITEGOBLIN_TOKEN_FILE` can override the path; `CITEGOBLIN_CLIENT_CONFIG` can point to a preconfigured desktop client JSON.

```sh
citegoblin auth-status
citegoblin logout
```

`auth-status` never displays tokens. `logout` removes the local token; it does not revoke Google's grant or stop an already-running process. Access can also be revoked in your Google Account's connected-app settings.

The current CLI requests `documents` and `drive` to edit existing URL-selected documents and manage comments without a per-file picker. CiteGoblin resolves successful citation and style command threads regardless of who wrote them; bibliography-location comments stay open. It never deletes comments or replies. Failed commands remain open with one maintained error reply. See [Google comment resolution](https://developers.google.com/workspace/drive/api/guides/manage-comments#resolve_a_comment).

For servers, existing Application Default Credentials remain available explicitly: set `CITEGOBLIN_AUTH=adc`, or set `GOOGLE_APPLICATION_CREDENTIALS` to an approved credentials file. These modes do not launch browser sign-in. A service account must have document editing and commenting access.

## External users and public release

The current maintainer registration is internal to CGPS. Supporting other accounts requires an External OAuth application configuration; changing a user's local cache location does not change that registration.

For a limited beta, configure an external testing project and add the intended Google accounts as test users. Google limits testing to 100 allowlisted users. Testing-mode refresh tokens normally expire after seven days for the scopes CiteGoblin requests, so testers may need to sign in again. Workspace administrators can also restrict access. See Google's [app-state overview](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview) and [refresh-token rules](https://developers.google.com/identity/protocols/oauth2#expiration).

For a public launch, prepare the app's branding, verified website domain, privacy policy, support contact, scope justification and demonstration of the consent flow and document features, then submit the required verification. The current full `drive` scope is **restricted**, so this requires more scrutiny than basic Google sign-in. See [Drive scope classifications](https://developers.google.com/workspace/drive/api/guides/api-specific-auth) and [restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification). Google determines review and any security-assessment requirements; configuration alone is not verification.

A possible public-release design is to use the narrower, non-sensitive `drive.file` scope and a Google file picker. That would authorise each selected file rather than all Drive files, but it needs a real file-selection flow: pasting an existing document URL alone does not grant per-file access. This design has not been implemented or live-tested. The current requested scopes remain unchanged.
