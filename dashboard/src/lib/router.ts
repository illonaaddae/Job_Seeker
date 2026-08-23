/**
 * Hash routing, hand rolled.
 *
 * Two routes and a drawer do not justify a router dependency, but they do
 * justify real URLs: refreshing the page should keep you where you were, and a
 * job you are reviewing should be linkable.
 *
 *   #/jobs            a view
 *   #/jobs/1420       a view with the review drawer open on that job
 */
import { useEffect, useState } from "react";

export interface Route {
  view: string;
  jobId: number | null;
}

function parse(hash: string): Route {
  const [view = "overview", id] = hash.replace(/^#\/?/, "").split("/");
  const jobId = id && /^\d+$/.test(id) ? Number(id) : null;
  return { view: view || "overview", jobId };
}

export function useRoute(): [Route, (route: Route) => void] {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash));

  useEffect(() => {
    const onChange = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const navigate = (next: Route) => {
    const hash = `#/${next.view}${next.jobId ? `/${next.jobId}` : ""}`;
    if (window.location.hash !== hash) window.location.hash = hash;
    else setRoute(next);
  };

  return [route, navigate];
}
