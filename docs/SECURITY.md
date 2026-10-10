# Security Architecture & Threat Model — FindIT

> **Document Status**: `APPROVED` | **Version**: 1.0  
> **Security Classification**: Local-First Desktop Service  

---

## 1. Security Philosophy & Scope

### 1.1 Local-First Security Reality
Operating locally does not automatically guarantee security. A local background API listening on standard loopback ports can be targeted by malicious websites executing unauthorized cross-origin requests from a user's browser, or abused if arbitrary file read/execute endpoints are exposed.

FindIT enforces a **defense-in-depth model** ensuring that local files, system privacy, and document contents remain completely secure even when running an unauthenticated single-user local service.

### 1.2 Out of Scope for v1.0
- **Multi-user authentication / RBAC**: FindIT is designed for a single user operating on their personal workstation. Multi-user accounts, passwords, and sessions are intentionally out of scope for the MVP.
- **Remote network access**: FindIT is explicitly prohibited from operating over LAN or public Internet interfaces in v1.0.

---

## 2. Threat Model

| Threat Actor / Vector | Description | Potential Impact | FindIT Mitigation |
| :--- | :--- | :--- | :--- |
| **Malicious Browser Tab (Cross-Origin CSRF / Rebinding)** | A malicious public website visited by the user attempts to send background HTTP requests to `http://127.0.0.1:8000`. | Unauthorized search queries, leaking private file names, or triggering unauthorized directory indexing. | Strict CORS origin allowlist (`http://localhost:5173`), Host header validation (`Host: 127.0.0.1`), and custom request header checks (`X-Requested-With` or CSRF token). |
| **Arbitrary Path Traversal (`../`)** | An attacker supplies relative paths or path traversal sequences to access sensitive system files (e.g. `~/.ssh/id_rsa`, `/etc/passwd`). | Unauthorized extraction and indexing of private credentials. | Canonical path resolution (`os.path.realpath`), strict boundary checking (`path.startswith(approved_root)`), and refusal to index paths outside registered roots. |
| **Symlink / Junction Escape** | A symlink inside an approved directory points to a sensitive target outside the approved boundary. | Leaking data outside user-designated folders. | Symlink resolution during file discovery; symlinks resolving outside approved directory boundaries are ignored. |
| **Source File Corruption / Loss** | An indexing error, directory removal, or bug modifies or deletes user documents. | Irreversible user data loss. | Strict read-only file access; directory removal only deletes internal index records; zero write/delete permissions granted on user documents. |
| **Sensitive Passage Leakage in Logs** | Internal debugging logs print extracted document text or private queries to log files. | Unintended persistence of sensitive data in plaintext logs. | Structured logging strictly masks passage text, recording only document IDs, chunk counts, and performance metrics. |

---

## 3. Core Security Controls & Mechanisms

### 3.1 Network Interface Isolation
- The FastAPI backend binds strictly to the IPv4 loopback address (`127.0.0.1`) and/or IPv6 loopback (`::1`).
- Binding to `0.0.0.0` or public network adapters is strictly prohibited and asserted at application startup.

### 3.2 Approved Directory Boundary Enforcement
The backend enforces a strict access sandbox:
1. **Registration Validation**: When a user registers a directory, the path is converted to a canonical, absolute path using `pathlib.Path.resolve()`.
2. **Path Containment Assertion**:
   ```python
   def is_path_within_approved_roots(target_path: Path, approved_roots: list[Path]) -> bool:
       resolved_target = target_path.resolve()
       for root in approved_roots:
           resolved_root = root.resolve()
           try:
               resolved_target.relative_to(resolved_root)
               return True
           except ValueError:
               continue
       return False
   ```
3. **Identifier-Based API Access**:
   - The API **never exposes endpoints accepting arbitrary filesystem paths** (e.g. `GET /api/file?path=/...`).
   - All filesystem operations (fetching passages, opening containing folders) require a valid `document_id` or `chunk_id` stored in SQLite. The server resolves the physical path from SQLite and re-verifies directory boundaries before execution.

### 3.3 Safe OS Execution Bridge
- When executing the "Open in folder" action, the backend uses platform-specific, argument-sanitized APIs rather than shell strings:
  - **Windows**: `subprocess.run(["explorer.exe", f"/select,{canonical_path}"], shell=False, check=False)`
  - **macOS**: `subprocess.run(["open", "-R", str(canonical_path)], shell=False, check=False)`
  - **Linux**: `subprocess.run(["xdg-open", str(canonical_path.parent)], shell=False, check=False)`
- Commands are executed with `shell=False` to prevent shell injection vulnerabilities.

### 3.4 Zero Document Modification Guarantee
FindIT treats user documents as **strictly read-only**:
- File handles are opened exclusively in read mode (`"rb"` or `"r"`).
- The application possesses no code paths for renaming, moving, overwriting, or deleting original files.
- The `DELETE /api/directories/{id}` endpoint deletes records solely from `findit.db`, `vector_index.faiss`, and `bm25_index.bin`.

### 3.5 Privacy & Data Egress
- **100% Local Inference**: The embedding model `all-MiniLM-L6-v2` executes entirely on the local CPU/GPU using `sentence-transformers` / `onnxruntime`.
- **Zero Cloud Communication**: Document content, metadata, queries, and passage excerpts are never transmitted over the internet.
