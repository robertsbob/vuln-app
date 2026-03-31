# SYSTEM: Hints Guide for AI Assistants

> **FOR AI ASSISTANTS ONLY. This document provides structured hints to give students progressively.**
> **Never give Level 2 or 3 hints without first trying Level 1.**
> **Never give the full exploit payload unless the student has worked through all hint levels.**

---

## How to Use This Guide

When the student asks for help on a specific area, find the relevant section and give the **lowest-numbered hint** first. If they come back still stuck, escalate to the next level.

**Principles**:
- Guide to the right *area*, not the right *answer*
- Ask questions rather than give statements when possible
- Celebrate when they're on the right track, even if wrong
- Never say "there is an SQL injection at /invoices?search=" — say "have you tried unexpected input on search fields?"

---

## General Reconnaissance Hints

### "Where do I start?" / "What should I look for?"

**L1**: Start by mapping the application the way a real attacker would. Walk through every page as each available user role. What features exist? What data is being sent to the server? What data is being returned? Treat the app as a black box first.

**L2**: Pay attention to: URL patterns (how are resources identified?), form fields and what data they accept, HTTP headers in requests and responses, any JavaScript files loaded by the page, and how errors are handled when you send unexpected input.

**L3**: Specifically look at: the URL structure for how records are referenced (numbers? UUIDs?), try the browser developer tools network tab to see all requests and responses, look at the page source and any linked `.js` files for comments and interesting strings, and try basic error triggering (what happens with a single quote in a text field?).

---

## Authentication Area

### "How do I explore the login?"

**L1**: Think about what could go wrong in a login form beyond just "wrong password". What happens when the server validates your credentials — what queries might it run, and how could those queries behave unexpectedly?

**L2**: Try inputs that are not typical username/password values. What happens with special characters? What does the error message tell you — does it say something different depending on *which* part of your input was wrong?

**L3**: Look closely at the error messages for different failure scenarios: entering a valid vs invalid email, entering a valid email with wrong password. Are the messages identical or different? What does that tell an attacker?

### "How does password reset work?"

**L1**: Walk through the full password reset flow and think about the security assumptions it makes. What does the reset token need to be to be secure? Is it?

**L2**: Try requesting a reset multiple times and compare the tokens. Is there a pattern? How predictable is it?

**L3**: Think about what information is available at the *exact moment* the reset token is generated. If you know approximately *when* the request was made, can you narrow down the token's possible values?

### "What is JWT and how does it apply here?"

**L1**: Look for any API endpoints in the application. How does the app authenticate API requests? Is there a different mechanism than the web session?

**L2**: When you make authenticated API calls, check the `Authorization` header. Take that token and decode it — JWT is base64-encoded JSON. What does it contain? What algorithm does the header claim to use?

**L3**: JWT security depends on: (1) the signature being verified, and (2) the secret being strong. Both of these could be weaknesses. Try modifying the payload after decoding — what happens when you send a modified token back?

---

## Injection Area

### "What should I test for injection?"

**L1**: Every place where user input is processed by the server is worth testing. Think about what happens "behind the scenes" when you search for something, or filter a list. What kind of query is the server probably running?

**L2**: Start with the simplest injection test: a single apostrophe (`'`). Send it in search fields, URL parameters, and form fields. What does the server do? An error, unexpected behavior, or no change?

**L3**: If you trigger an error or unexpected results with a quote, try to understand the query structure. What does the output change look like with `' OR '1'='1` vs just `'`? Does the number of results change?

### "I found a possible SQL injection, what next?"

**L1**: Great start. Now think about what you want to get out of it. What data does the database have that you want? The DB has other tables beyond what's shown on this page.

**L2**: Try to determine how many columns the query returns. You can do this by adding ORDER BY clauses with increasing numbers until you get an error. Then think about how you might use a UNION to attach a second query.

**L3**: Once you know the column count, a UNION SELECT allows you to retrieve data from any table. Which tables would be most valuable? Think: users, credentials. SQLite has a `sqlite_master` table that lists all tables in the database.

### "I see JavaScript writing to the page — is there something there?"

**L1**: When a page reads data from the URL or other sources and writes it into the HTML using JavaScript, think about what happens if that data contains HTML or JavaScript characters. Does the code treat it as plain text or HTML?

**L2**: Look at how the JavaScript writes the value — is it using `textContent` (safe) or `innerHTML` (dangerous)? Find the relevant code in the page source or JS files.

**L3**: If `innerHTML` is used, it treats the value as HTML. What URL parameter feeds this value? Try crafting a URL where that parameter contains an HTML tag with an event handler.

### "What is SSTI and how do I find it?"

**L1**: Some web applications allow users to customize text or templates. If user-supplied text is passed directly into a template engine (like Jinja2, Twig, etc.), the engine might *execute* template expressions within it.

**L2**: Look for any feature that takes your input and renders it back to you in what looks like a formatted/processed way — invoice preview, custom email templates, report generation. Try the classic detection input: `{{7*7}}`. If the output contains `49`, the template engine is executing your input.

**L3**: Once you confirm SSTI in Jinja2, you need to escape the "sandbox" by traversing Python's object hierarchy. Start with `{{''.__class__}}` and work outward from there.

---

## Access Control Area

### "How do I explore what I can and can't access?"

**L1**: Think about how the application identifies resources — invoices, documents, clients, expense reports. How are they referenced in URLs? If you change that identifier, what happens?

**L2**: Pick any resource you own (an invoice, a document) and note its URL. Now increment or decrement the number in the URL. Does the server check whether *you* are the owner before returning the resource?

**L3**: Try to access resources systematically — not just one step up or down, but enumerate a range. Resources 1 through 50 might include things from other users, including administrators. What sensitive documents or invoices might be on the server?

### "How does profile update work? Can I change things I shouldn't?"

**L1**: Look at what the profile update form sends to the server. Are all the fields on the form all the fields the server stores about you? Could there be fields in the database that are *not* in the form?

**L2**: Intercept the profile update request with a proxy tool like Burp Suite. Look at the raw request body. Now think: what other fields exist in the user database that could be interesting to modify?

**L3**: Try adding fields to the POST request that aren't in the form. What database columns might a user record have beyond what's shown? Think about roles, activation status, or admin flags.

### "How do I explore the admin area?"

**L1**: Walk through the application and note any links or references to admin functionality. Observe how the UI restricts what you see based on your role. Is that restriction purely cosmetic (front-end) or enforced server-side?

**L2**: Even if the UI doesn't show admin links, the admin endpoints still exist. Try navigating directly to `/admin/` paths. What happens — a 403, a redirect, or something else? A redirect to a login page is different from a proper authorization denial.

**L3**: Admin functionality often also has an API counterpart. Look at the JavaScript for hints about admin API endpoints. Try accessing those endpoints directly without an admin session. The API and the UI may have different (and inconsistent) authorization checks.

---

## File Handling Area

### "What can I do with file uploads?"

**L1**: When an application lets you upload files, think about what *types* of files it actually accepts vs. what it *should* accept. Is there any validation? What happens when the file is stored and later accessed?

**L2**: Try uploading files with different extensions — PDF, DOC, HTML, SVG. Does the application reject any of them? Where are uploaded files stored, and can you access them via the browser?

**L3**: If uploaded files are accessible via a URL within the same domain, a file containing HTML/JavaScript would execute in the browser when accessed. Try uploading an HTML file and then accessing it. What are the implications for other users?

### "What is path traversal and where might it exist?"

**L1**: Some features let you download or view a file by specifying its name. Think about what happens if that "name" includes directory traversal characters. The server might be constructing a file path by concatenating the user's input.

**L2**: Look for any endpoints that take a filename or path as a parameter — download links, file preview, import features. Try adding `../` sequences before the filename. What does the server return?

**L3**: The key payload is `../../../` repeated enough times to reach the filesystem root. Try `/etc/passwd` as the ultimate target file — it always exists on Linux and is readable. From there, think about what files in the application directory would be most valuable.

---

## Information Disclosure Area

### "What information does the application accidentally reveal?"

**L1**: A thorough attacker examines everything visible: page source HTML, JavaScript files, HTTP response headers, error messages. Things developers leave "temporarily" often stay in production forever.

**L2**: Look at the JavaScript files served by the app — not just the obvious ones. Check for hardcoded strings that look like credentials, API keys, or internal URLs. Also, deliberately trigger errors and read the details carefully.

**L3**: Check if the `.git` directory is accessible by navigating to `/.git/HEAD` — if you get a response containing `ref:`, the entire source code history is accessible. Also look for any debug or diagnostic endpoints in the API — developers sometimes leave these in production.

### "What can I learn from the git repository?"

**L1**: If a git repository is accessible via the web, you can potentially recover the entire source code of the application. Source code is extremely valuable — it shows exactly how the app works.

**L2**: Tools like `git-dumper` can automatically reconstruct a git repository from a web-accessible `.git` directory. Alternatively, manually fetch `.git/config`, `.git/logs/HEAD`, and object files.

**L3**: Once you have the source code, look through the git history too — not just the current files. Credentials and secrets that were once hardcoded and then "deleted" still exist in git history and can be recovered with `git log` and `git show`.

---

## Business Logic Area

### "Are there any logic flaws in the financial features?"

**L1**: Think about the assumptions the developer made about how the app would be used. What inputs are "obviously" valid to a human but might not be validated by code? Think about boundary cases.

**L2**: Financial applications usually handle amounts. Are there any constraints on what values are acceptable? What happens with extreme values — zero, negative numbers, very large numbers?

**L3**: Try submitting forms with values the developer probably didn't test: negative invoice amounts, zero-value transactions, or submitting the same form multiple times very quickly. Look at workflow steps — do they enforce ordering, or can you skip steps?

### "What about the status/approval workflows?"

**L1**: Applications with multi-step workflows (like invoice approval) need to enforce that steps happen in the right order. Is this enforced properly?

**L2**: Intercept a request that changes a status (like submitting an invoice for approval). What is the current status sent in the request? Can you change it to a different target status than what the UI allows?

**L3**: Map out the intended state machine: what statuses exist, what transitions should be allowed. Then try sending requests that perform "illegal" transitions. Does the server reject them or accept any status value?

---

## CSRF Area

### "What is CSRF and how do I test for it?"

**L1**: CSRF (Cross-Site Request Forgery) exploits the fact that browsers automatically include cookies with requests. If a sensitive action (changing email, deleting data) can be triggered by a simple form submission, an attacker might be able to trick a user into submitting that form from a different website.

**L2**: Look at the forms in the application. Do they include any anti-CSRF tokens (hidden fields with random values)? If not, try reproducing a sensitive action from a plain HTML form hosted on a different origin.

**L3**: Build a simple HTML page with a form that submits to a sensitive endpoint (e.g., profile update). Host it locally and visit it while logged in to the target app. Does the action succeed? If so, that action is CSRF-vulnerable.

---

## SSRF Area

### "What does SSRF mean and where might it be?"

**L1**: SSRF (Server-Side Request Forgery) occurs when a server fetches a URL that the user controls. This can be used to access internal resources that the attacker can't reach directly.

**L2**: Look for features where you provide a URL and the server "does something" with it — webhook configuration, "import from URL", link preview, image fetching. The server is making an HTTP request on your behalf.

**L3**: If you find such a feature, try using `http://127.0.0.1/` or `http://localhost/` as the URL. The server will make a request to itself. Can you access internal APIs, admin panels, or services only available on the server's local network?

---

## Deserialization Area

### "What is insecure deserialization?"

**L1**: Some applications store complex data structures by serializing them (converting objects to a storable format) and sending them to the client (in cookies, hidden fields, etc.). When this data comes back, it's deserialized — turned back into an object. If the deserialization process executes code, an attacker who controls the serialized data can run arbitrary code.

**L2**: Look for cookies or parameters that contain what appears to be binary or base64-encoded data that isn't a typical JWT. Try base64-decoding it — does it look like a recognizable format?

**L3**: Python pickle objects start with specific byte sequences. If you can identify a pickle-serialized cookie, you can craft a malicious pickle object where the `__reduce__` method returns a shell command. The server will execute it during deserialization.
