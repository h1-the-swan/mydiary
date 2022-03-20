import React, { FC } from "react";
import {
  Layout,
  Menu,
  Table,
  TableColumnGroupType,
  TableColumnProps,
  TableColumnType,
  TableProps,
} from "antd";
import "./App.css";
import { PocketArticleRead, useReadPocketArticles, useReadTags } from "./api";

const { Header, Content, Footer, Sider } = Layout;

// function App() {
//   return (
//     <div className="App">
//       <header className="App-header">
//         <img src={logo} className="App-logo" alt="logo" />
//         <p>
//           Edit <code>src/App.tsx</code> and save to reload.
//         </p>
//         <a
//           className="App-link"
//           href="https://reactjs.org"
//           target="_blank"
//           rel="noopener noreferrer"
//         >
//           Learn React
//         </a>
//       </header>
//     </div>
//   );
// }

// const Tags = () => {
//   const { data: tags, isLoading } = useReadTags(
//     {},
//     { query: { select: (d) => d.data } }
//   );
//   if (!tags) return null;
//   const items = tags.map((tag) => (
//     <p>
//       {tag.id} | {tag.is_pocket_tag} | {tag.name}
//     </p>
//   ));
//   return <div>{items}</div>;
// };

const PocketArticlesTable = () => {
  const { data: articles, isLoading } = useReadPocketArticles(
    {},
    {
      query: {
        select: (d) => d.data,
      },
    }
  );
  if (!articles) return null;
  const columns: TableColumnType<PocketArticleRead>[] = [
    {
      title: "id",
      dataIndex: "id",
      key: "id",
    },
    {
      title: "given_title",
      dataIndex: "given_title",
      key: "given_title",
    },
    {
      title: "resolved_title",
      dataIndex: "resolved_title",
      key: "resolved_title",
    },
  ];
  return <Table dataSource={articles} columns={columns} />;
};

const App: FC = () => (
  <Layout>
    <Sider
      breakpoint="lg"
      collapsedWidth="0"
      onBreakpoint={(broken) => {
        console.log(broken);
      }}
      onCollapse={(collapsed, type) => {
        console.log(collapsed, type);
      }}
    >
      <div className="logo" />
      <Menu theme="dark" mode="inline" defaultSelectedKeys={["4"]}>
        <Menu.Item key="1">nav 1</Menu.Item>
        <Menu.Item key="2">nav 2</Menu.Item>
        <Menu.Item key="3">nav 3</Menu.Item>
        <Menu.Item key="4">nav 4</Menu.Item>
      </Menu>
    </Sider>
    <Layout>
      <Header
        className="site-layout-sub-header-background"
        style={{ padding: 0 }}
      />
      <Content style={{ margin: "24px 16px 0" }}>
        <div
          className="site-layout-background"
          style={{ padding: 24, minHeight: 360 }}
        >
          <PocketArticlesTable />
        </div>
      </Content>
      <Footer style={{ textAlign: "center" }}>
        Ant Design ©2018 Created by Ant UED
      </Footer>
    </Layout>
  </Layout>
);

export default App;
