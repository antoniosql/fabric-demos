import { PublicClientApplication, type AccountInfo } from '@azure/msal-browser';

export type RagEvidence = {
  documentCode: string;
  documentTitle: string;
  chunkNumber: number;
  score: number;
  excerpt: string;
};

export type RagAnswer = {
  returnCaseId: string;
  question: string;
  recommendation: string;
  confidence: number;
  requiresManualReview: boolean;
  reasons: string[];
  nextActions: string[];
  evidence: RagEvidence[];
  auditId?: number;
  generatedAtUtc?: string;
  modelName?: string;
  operationalContext?: Record<string, unknown>;
  retrievedChunks?: unknown[];
};

const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID as string;
const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID as string;
const udfUrl = import.meta.env.VITE_UDF_FUNCTION_URL as string;

const msal = new PublicClientApplication({
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: window.location.origin
  },
  cache: {
    cacheLocation: 'sessionStorage'
  }
});

let initialized = false;
async function ensureMsal() {
  if (!initialized) {
    await msal.initialize();
    initialized = true;
  }
}

async function getToken(): Promise<string> {
  await ensureMsal();
  const scopes = ['https://analysis.windows.net/powerbi/api/.default'];
  let account: AccountInfo | null = msal.getActiveAccount();
  if (!account) {
    const accounts = msal.getAllAccounts();
    account = accounts[0] ?? null;
  }
  if (!account) {
    const login = await msal.loginPopup({ scopes });
    account = login.account;
    msal.setActiveAccount(account);
  }
  try {
    const result = await msal.acquireTokenSilent({ scopes, account });
    return result.accessToken;
  } catch {
    const result = await msal.acquireTokenPopup({ scopes, account });
    return result.accessToken;
  }
}

export function isConfigured(): boolean {
  return Boolean(udfUrl && clientId && tenantId && !clientId.startsWith('00000000'));
}

export async function answerReturnCase(returnCaseId: string, question: string): Promise<RagAnswer> {
  if (!isConfigured()) {
    throw new Error('La app no tiene VITE_UDF_FUNCTION_URL / VITE_ENTRA_CLIENT_ID / tenant de Entra configurados.');
  }
  const token = await getToken();
  const response = await fetch(udfUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({ returnCaseId, question, maxChunks: 6 })
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error?.message || data?.message || `HTTP ${response.status}`);
  }
  return (data.output ?? data) as RagAnswer;
}
