| Flow / Grant Type    | Best Use Case            | Security Status | Description                                                |
|----------------------|--------------------------|-----------------|------------------------------------------------------------|
| Authorization Code   | Server-side web apps     | Recommended     | Exchanges a code for a token on the backend server.        |
| Auth Code + PKCE     | Mobile, SPA, Desktop     | Required (2.1)  | Adds a Proof Key to prevent code interception/injection.   |
| Client Credentials   | Machine-to-Machine (M2M) | Recommended     | App authenticates as itself to access its own resources.   |
| Device Code          | Smart TVs, CLI, IoT      | Recommended     | Login via a secondary device for input-limited hardware.   |
| Implicit Flow        | Legacy SPAs              | Deprecated      | Tokens sent in URL; high risk of leakage and interception. |
| Password (ROPC)      | Legacy trusted apps      | Deprecated      | App handles raw passwords; high security risk, no MFA.     |

# 1. Authz code
#### BFF (Backend For Frontend) Pattern
1. `Resource Owner`: The human user.
2. `User Agent`: The Angular app running in the browser.
3. `OAuth2 Client`: The API Gateway (Spring Cloud Gateway). It holds the client_id and client_secret.
4. `Authorization`: Server: Okta. It has the /authorize and /token endpoints.
5. `Resource Server`: Your Microservice. It accepts JWTs but doesn't handle logins.

#### Flow
[Flow](OAuth2-AuthCode-1.png)
1. Initiation: Angular redirects the browser to https://my-gateway.com/oauth2/authorization/okta.
2. Redirect to Okta: The Gateway sees this, builds the full Okta URL (with client_id, state, redirect_uri), and sends the user to Okta's /authorize page.
3. Login: User enters credentials on Okta’s page.
4. Code Return: Okta redirects the browser back to the Gateway (e.g., /login/oauth2/code/okta) with a ?code=XYZ.
5. Token Exchange: The Gateway intercepts that code and calls Okta's /token endpoint (POST) using its client_secret.
6. Session Creation: Okta gives the Gateway a JWT Access Token. The Gateway saves this token in a secure session (like Redis) and sends an Encrypted HttpOnly Cookie back to Angular.
7. Resource Call: When Angular calls GET /deals, it sends the Cookie. The Gateway swaps the Cookie for the JWT and sends the JWT to your microservice.

### Pre-registration

1. The Core Registration Trio:When you register your "Web Application" in the Okta Admin Console, you must define:
    - Client ID: The public identifier (e.g., 0oa123...). Think of this as the "Username" for your Gateway.
    - Client Secret: The private password for your Gateway. Must never be shared or put in frontend code.
    - Redirect URI: The specific endpoint on your Gateway that Okta is allowed to send the code to (e.g., https://api.myapp.com/login/oauth2/code/okta). 
        - The redirect_uri is not just a random string; it is the designated delivery address for the secret code. If it doesn't point directly to the Gateway's OAuth2 callback endpoint, the chain of trust is broken.
        - Read 

2. Beyond the Trio (The "Fine Print")
    - Grant Type: You must explicitly enable "Authorization Code."
    - Allowed Scopes: You define which permissions the Gateway is allowed to ask for (e.g., openid, profile, email, or custom ones like deals:create).
    - Issuer URL: This is the Okta-provided URL (e.g., https://dev-12345.okta.com/oauth2/default) that the Gateway uses to find the /authorize and /token endpoints.

4. Summary for your Spring Gateway application.yml
You take these pre-registered values and plug them into your Gateway like this:

```yml
spring:
  security:
    oauth2:
      client:
        registration:
          okta:
            client-id: ${OKTA_CLIENT_ID}
            client-secret: ${OKTA_CLIENT_SECRET}
            scope: openid, profile, email
            redirect-uri: "{baseUrl}/login/oauth2/code/{registrationId}"
        provider:
          okta:
            issuer-uri: https://${OKTA_DOMAIN}/oauth2/default
# store that client-secret in AWS (e.g., using Secrets Manager or Parameter Store)?
```

### The "Scheme Mismatch" Trap
- When your Gateway generates the redirect_uri to send to Okta, it looks at the current request's scheme.
- The Reality: User → (HTTPS) → ALB → (HTTP) → Gateway
- The Error: The Gateway sees a request coming in via http and tells Okta: "Send the code to http://api.myapp.com/...."
- The Result: Okta rejects this because http is not in your pre-registered list of allowed https redirect URIs. 

**Solution: Forwarded Header Strategy**

- You need to tell Spring to "listen" to the ALB. The ALB automatically attaches headers to tell the backend what the original request looked like:
    * `X-Forwarded-Proto:` (will be https) and `X-Forwarded-Port`: (will be 443)
    * Add this to your Gateway's application.yml:
    ```yml
    server:
        # This tells Spring to trust the headers sent by the proxy (ALB)
        # Spring Security and Spring Web will manually check the headers and swap the http:// for https://
        # before building the OAuth2 request. It is the most reliable way to fix the "mismatch" in a Spring Cloud Gateway.
        forward-headers-strategy: framework
    ```
**Verification Check**
- After adding this setting, the flow changes to: 
    - ALB receives HTTPS request.
    - ALB sends request to Fargate with X-Forwarded-Proto: https.
    - Spring Gateway reads the header and correctly builds the redirect_uri as https://api.myapp.com/....
    - Okta validates the URI, matches it to your pre-registry, and allows the user to log in.


| Step | Phase                | Request (Example)               | Response (Example)              | Description                                                |
|------|----------------------|---------------------------------|---------------------------------|------------------------------------------------------------|
| 1    | Trigger Login        | GET /oauth2/authorization/okta  | 302 Redirect to Okta            | Angular redirects the browser to the Gateway's login       |
|      |                      |                                 |                                 | entry point to start the flow.                             |
| 2    | Authorize Request    | GET {Okta}/v1/authorize?        | 200 Login Page                  | Gateway redirects browser to Okta with client_id,          |
|      |                      | client_id=ABC&state=XYZ...      |                                 | redirect_uri, and scopes.                                  |
| 3    | User Authentication  | POST /login (Credentials)       | 302 Redirect to Gateway         | User logs into Okta. Okta redirects browser back to        |
|      |                      |                                 | Location: ...?code=123          | Gateway's redirect_uri with an Auth Code.                  |
| 4    | Token Exchange       | POST {Okta}/v1/token            | 200 { "access_token": "...",    | **Back-channel:** Gateway sends Auth Code + Client Secret  |
|      |                      | code=123&client_secret=SHH...   | "id_token": "..." }             | to Okta to get the actual JWT tokens.                      |
| 5    | Session Creation     | (Internal to Gateway)           | 302 Redirect to Angular UI      | Gateway saves tokens in session (Redis) and sends an       |
|      |                      |                                 | Set-Cookie: SESSION=XYZ         | HttpOnly session cookie to the browser.                    |
| 6    | API Call             | GET /api/deals                  | (Request forwarded with JWT)    | Angular calls Gateway with the Cookie. Gateway swaps       |
|      |                      | Cookie: SESSION=XYZ             |                                 | cookie for Bearer JWT and calls Microservice.              |

- `Token Relay`: Use the `TokenRelay` filter in your Gateway routes. This ensures that the Gateway automatically extracts the JWT from its session and adds it as an    `Authorization: Bearer <token>` header before the request hits your Fargate microservices.
- Security: By using the BFF (Backend For Frontend) pattern, your Angular app never sees the Access Token, which protects you from XSS attacks that target local storage.


### How openid changes the flow
- Adding openid to the scope turns "OAuth 2.0" into OpenID Connect (OIDC).
- The Payload: You get back an ID Token in addition to the Access Token. Identity: The ID Token contains user info (name, email, etc.).
- **IMPORTANT** The Flow: The sequence remains the same, but the Gateway now gains the ability to call Okta's `/userinfo` endpoint automatically to populate the user's profile in the backend session.

### cURL Commands
1. Step A: Initiate Authorize (Done by Browser Redirect). This is what the Gateway generates when the user clicks login.

```bash
# This is usually done via browser redirect, not manual cURL
curl -v "https://{OKTA_DOMAIN}/v1/authorize? \
  response_type=code& \
  client_id={CLIENT_ID}& \
  scope=openid%20profile%20email& \
  state={RANDOM_STATE}& \
  redirect_uri=https://{GATEWAY}/login/oauth2/code/okta"

HTTP/1.1 302 Found
Location: https://{GATEWAY}/login/oauth2/code/okta?code=xYz123&state=af0ifjsldkj
```  
2. Step B: Exchange Code for Token (Done by Gateway Server). The Gateway calls this behind the scenes.

```bash
curl -X POST "https://{OKTA_DOMAIN}/v1/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -u "{CLIENT_ID}:{CLIENT_SECRET}" \
     -d "grant_type=authorization_code" \
     -d "code={CODE_FROM_STEP_A}" \
     -d "redirect_uri=https://{GATEWAY}/login/oauth2/code/okta"

response = {
  "access_token": "eyJhbG...", 
  "id_token": "eyJraW...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```
3. The Actual API Call (From Angular to Gateway). Angular simply makes a call with the Cookie.
```bash
curl -v "https://{GATEWAY}/api/deals" \
     -H "Cookie: SESSION={GATEWAY_SESSION_ID}"
```
4. Step D: What the Microservice sees: The Gateway adds the Bearer Token here.

```bash
# The Gateway transforms Step C into this before sending to Fargate:
GET /api/deals HTTP/1.1
Host: microservice-internal
Authorization: Bearer eyJhbG... [THE JWT]
``
### Tutorials
- Dan Vega - basic login by github and google - https://www.youtube.com/watch?v=us0VjFiHogo
- Here we use OAuth client Lib and also the REST end points are here so the springboot is both OAuth2 client and Resource Server
- Note that `oauth2Login()` is the trigger for the BFF pattern in Spring Security.
- If you use `oauth2ResourceServer()`, you are telling Spring: "I am a Microservice, give me a JWT."
- If you use `oauth2Login()`, you are telling Spring: "I am a BFF, I will handle the login and manage the session for the user."
