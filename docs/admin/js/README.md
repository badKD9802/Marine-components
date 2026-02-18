# Admin JavaScript Modules

This directory contains modularized JavaScript files for the admin panel.

## File Structure

### Core Files

1. **api.js** (957 bytes)
   - API base configuration (`API_BASE`)
   - Authentication token management (`authToken`)
   - Authenticated API request function (`api()`)
   - HTML escaping utility (`esc()`)

2. **init.js** (3.6 KB)
   - Application initialization
   - Dark mode toggle and initialization
   - Upload card setup (drag & drop)
   - Tab switching logic
   - DOMContentLoaded event handlers
   - Keyboard event listeners

### Feature Modules

3. **auth.js** (1.6 KB)
   - Login handling (`handleLogin()`)
   - Logout handling (`handleLogout()`, `logout()`)
   - Dashboard display (`showDashboard()`, `showLogin()`)
   - Session token management

4. **dashboard.js** (1.4 KB)
   - Dashboard statistics loading (`loadDashboardStats()`)
   - Statistics display for mails, documents, RAG conversations, inquiries

5. **docs.js** (9.6 KB)
   - Document upload and management (`uploadFile()`, `handleFiles()`)
   - Document list rendering (`loadDocuments()`, `renderDocuments()`)
   - Document detail view (`viewDocument()`)
   - Chunk editing (`startChunkEdit()`, `saveChunkEdit()`, `cancelChunkEdit()`)
   - Document deletion (`deleteDocument()`)
   - RAG document management (`loadRagDocuments()`, `renderRagDocuments()`)
   - Mail document management (`loadMailDocuments()`, `renderMailDocuments()`)
   - Document selection (`getSelectedDocIds()`, `getMailSelectedDocIds()`)

6. **rag.js** (20 KB)
   - Conversation management (`loadConversations()`, `createConversation()`, `deleteConversation()`)
   - Conversation rendering (`renderConversations()`, `renderChatMessages()`)
   - Conversation operations (rename, save/unsave, select)
   - Chat interface (`sendRagMessage()`, `switchToChatMode()`)
   - Welcome screen (`showWelcomeScreen()`, `renderWelcomeDocs()`)
   - Message rendering (`appendMsg()`, `updateMsg()`, `renderMd()`)
   - Reference popup (`showRefChunks()`, `openRefPopup()`, `closeRefPopup()`)
   - Kebab menu (`toggleKebab()`, `closeAllKebabs()`)
   - Typing indicator (`showTyping()`)
   - Markdown rendering with marked.js and DOMPurify

7. **inquiry.js** (5.8 KB)
   - Inquiry list loading (`loadAdminInquiries()`, `loadInquiryDetail()`)
   - Inquiry rendering (`renderAdminInquiries()`)
   - Reply panel (`openAdminReply()`, `closeAdminReply()`)
   - Reply submission (`submitAdminReply()`, `replyInquiry()`)
   - Inquiry deletion (`deleteAdminInquiry()`)
   - HTML escaping for inquiries (`escapeHtmlAdmin()`)

8. **products.js** (15 KB)
   - Product CRUD operations (`loadProducts()`, `createProduct()`, `updateProduct()`, `deleteProduct()`)
   - Product rendering (`renderProducts()`)
   - Product form (`showProductForm()`, `editProduct()`, `saveProduct()`)
   - Category management (`loadCategories()`, `addCategory()`, `deleteCategory()`)
   - Image upload (`handleImageFile()`, `handleImageUpload()`, `setupImageDropZone()`)
   - Product search and filtering
   - Modal management (`closeProductModal()`)

9. **mail.js** (59 KB) - Largest module
   - Mail composition (`composeMail()`, `recomposeMail()`)
   - Mail translation (`translateMail()`, `translateIncoming()`)
   - Mail history (`loadMailHistory()`, `renderMailHistory()`, `loadMailHistoryItem()`)
   - Draft management (`saveMailComposition()`, `copyMailDraft()`)
   - Gmail integration:
     - Connection (`gmailConnect()`, `gmailDisconnect()`)
     - Status (`loadGmailStatus()`, `updateGmailUI()`)
     - Inbox (`loadInboxEmails()`, `renderInboxList()`, `loadInboxItem()`)
     - Auto-fetch toggle (`toggleGmailAuto()`, `gmailFetch()`)
     - Reply (`sendMailReply()`, `toggleMailHtmlView()`)
   - Template management:
     - CRUD (`loadTemplates()`, `saveTemplate()`, `editTemplate()`, `deleteTemplate()`)
     - Rendering (`renderTemplates()`, `filterTemplates()`)
     - Usage (`useTemplate()`)
   - Signature management:
     - CRUD (`loadSignatures()`, `saveSignature()`, `editSignature()`, `deleteSignature()`)
     - Rendering (`renderSignatures()`, `updateSignatureDropdown()`)
     - Insertion (`insertSignature()`, `getDefaultSignature()`)
   - Prompt example management:
     - CRUD (`loadPromptExamples()`, `savePromptExample()`, `editPromptExample()`, `deletePromptExample()`)
     - Rendering (`renderPromptExamples()`)
   - UI helpers:
     - Sidebar (`toggleMailSidebar()`, `showMailPanel()`, `hideMailPanel()`)
     - Loading states (`showMailLoading()`, `hideMailLoading()`)
     - Language badge (`updateTargetLangBadge()`)

10. **settings.js** (4.8 KB)
    - Site settings loading (`loadSiteSettings()`)
    - Logo management (`loadSiteLogo()`, `saveLogo()`)
    - Company info (`saveCompanyInfo()`)
    - Hero section (`saveHeroSection()`)
    - Other settings (`saveOtherSettings()`)

11. **logs.js** (1.9 KB)
    - Mail logs loading (`loadMailLogs()`)
    - Log rendering with tone and language information

## Global Variables

Shared across modules (defined in respective files):
- `authToken` (api.js) - Authentication token
- `API_BASE` (api.js) - API base URL
- `currentConvId` (rag.js) - Current RAG conversation ID
- `ragDocuments` (rag.js) - RAG documents array
- `siteLogoUrl` (rag.js/settings.js) - Site logo URL
- `allProducts` (products.js) - Products array
- `allCategories` (products.js) - Categories array
- `mailDocuments` (mail.js) - Mail documents array
- `mailTemplates` (mail.js) - Mail templates array
- `mailSignatures` (mail.js) - Mail signatures array
- `promptExamples` (mail.js) - Prompt examples array
- `currentMailHistoryId` (mail.js) - Current mail history ID
- `currentAdminInquiryId` (inquiry.js) - Current inquiry ID
- `siteSettings` (settings.js) - Site settings object

## Load Order

Scripts should be loaded in this order in index.html:

1. api.js (core utilities)
2. auth.js
3. dashboard.js
4. docs.js
5. rag.js
6. inquiry.js
7. products.js
8. mail.js
9. settings.js
10. logs.js
11. init.js (must be last - sets up event listeners)

## Dependencies

- External libraries (loaded via CDN):
  - marked.js (Markdown parsing)
  - DOMPurify (HTML sanitization)

## Notes

- All files use "use strict" mode
- Functions maintain backward compatibility where applicable
- Error handling with try-catch blocks
- Consistent naming conventions (camelCase)
- Korean comments and user-facing text
