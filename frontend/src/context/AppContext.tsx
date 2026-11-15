import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, getStoredToken, setStoredToken } from "../lib/api";
import type {
  DailyCheckResponse,
  HealthStatus,
  OnboardSyllabusResponse,
  SyllabusGraphOut,
  SyllabusOut,
  UserOut,
} from "../types/api";

export type NavTab =
  | "dashboard"
  | "onboarding"
  | "tutor"
  | "graph"
  | "planner"
  | "resources"
  | "assessments"
  | "analytics"
  | "parent"
  | "traces";

interface AppContextValue {
  user: UserOut | null;
  health: HealthStatus | null;
  syllabi: SyllabusOut[];
  activeSyllabus: SyllabusOut | null;
  activeGraph: SyllabusGraphOut | null;
  activeTab: NavTab;
  loadingAuth: boolean;
  loadingWorkspace: boolean;
  latestSimulation: DailyCheckResponse | null;
  pendingDiagnostic: OnboardSyllabusResponse | null;
  setActiveTab: (tab: NavTab) => void;
  setLatestSimulation: (sim: DailyCheckResponse | null) => void;
  setPendingDiagnostic: (diag: OnboardSyllabusResponse | null) => void;
  onAuthenticated: (token: string, loggedUser: UserOut) => Promise<void>;
  refreshWorkspace: (targetSyllabusId?: string) => Promise<void>;
  switchSyllabus: (syllabusId: string) => Promise<void>;
  logout: () => void;
}

const AppContext = createContext<AppContextValue | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [syllabi, setSyllabi] = useState<SyllabusOut[]>([]);
  const [activeSyllabus, setActiveSyllabus] = useState<SyllabusOut | null>(null);
  const [activeGraph, setActiveGraph] = useState<SyllabusGraphOut | null>(null);
  const [activeTab, setActiveTab] = useState<NavTab>("dashboard");
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);
  const [latestSimulation, setLatestSimulation] = useState<DailyCheckResponse | null>(null);
  const [pendingDiagnostic, setPendingDiagnostic] = useState<OnboardSyllabusResponse | null>(null);

  const loadHealth = useCallback(async () => {
    try {
      const h = await api.health();
      setHealth(h);
    } catch {
      setHealth(null);
    }
  }, []);

  const refreshWorkspace = useCallback(
    async (targetSyllabusId?: string) => {
      setLoadingWorkspace(true);
      try {
        const [me, list] = await Promise.all([api.me(), api.listSyllabi()]);
        setUser(me);
        setSyllabi(list);

        if (list.length === 0) {
          setActiveSyllabus(null);
          setActiveGraph(null);
          if (me.role === "student") {
            setActiveTab("onboarding");
          }
          return;
        }

        const preferredId =
          targetSyllabusId || me.student_profile?.active_syllabus_id || list[0].id;
        const chosen = list.find((s) => s.id === preferredId) || list[0];
        setActiveSyllabus(chosen);

        const graph = await api.getSyllabusGraph(chosen.id);
        setActiveGraph(graph);
      } finally {
        setLoadingWorkspace(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadHealth();
    const token = getStoredToken();
    if (!token) {
      setLoadingAuth(false);
      return;
    }
    api
      .me()
      .then(async (me) => {
        setUser(me);
        if (me.role === "parent_teacher") {
          setActiveTab("parent");
        }
        await refreshWorkspace();
      })
      .catch(() => {
        setStoredToken(null);
        setUser(null);
      })
      .finally(() => setLoadingAuth(false));
  }, [loadHealth, refreshWorkspace]);

  const onAuthenticated = useCallback(
    async (token: string, loggedUser: UserOut) => {
      setStoredToken(token);
      setUser(loggedUser);
      setLatestSimulation(null);
      setPendingDiagnostic(null);
      setActiveTab(loggedUser.role === "parent_teacher" ? "parent" : "dashboard");
      await refreshWorkspace();
    },
    [refreshWorkspace],
  );

  const switchSyllabus = useCallback(
    async (syllabusId: string) => {
      setLatestSimulation(null);
      if (user?.role === "student") {
        await api.activateSyllabus(syllabusId);
      }
      await refreshWorkspace(syllabusId);
    },
    [refreshWorkspace, user],
  );

  const logout = useCallback(() => {
    setStoredToken(null);
    setUser(null);
    setSyllabi([]);
    setActiveSyllabus(null);
    setActiveGraph(null);
    setLatestSimulation(null);
    setPendingDiagnostic(null);
    setActiveTab("dashboard");
  }, []);

  return (
    <AppContext.Provider
      value={{
        user,
        health,
        syllabi,
        activeSyllabus,
        activeGraph,
        activeTab,
        loadingAuth,
        loadingWorkspace,
        latestSimulation,
        pendingDiagnostic,
        setActiveTab,
        setLatestSimulation,
        setPendingDiagnostic,
        onAuthenticated,
        refreshWorkspace,
        switchSyllabus,
        logout,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error("useApp must be used inside AppProvider.");
  }
  return ctx;
}
