import { Refine } from "@pankod/refine-core";
import { notificationProvider, Layout } from "@pankod/refine-antd";
import routerProvider from "@pankod/refine-react-router";
import "@pankod/refine-antd/dist/styles.min.css";
import dataProvider from "@pankod/refine-simple-rest";
import { PocketArticleList } from "pages/pocket/articles/list";

function App() {
  return (
    <Refine
      routerProvider={routerProvider}
      notificationProvider={notificationProvider}
      Layout={Layout}
      dataProvider={dataProvider("http://localhost:8080/api")}
      resources={[
        {
          name: "pocket/articles",
          list: PocketArticleList,
        }
      ]}
    />
  );
}

export default App;
