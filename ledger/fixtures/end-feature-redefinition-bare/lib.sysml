library package Lib {
  private import ScalarValues::*;
  private import Connections::BinaryConnection;
  private import Objects::BinaryLinkObject;

  part def Foo { attribute name : String; }

  connection def Link :> BinaryConnection {
    end source : Foo :>> BinaryLinkObject::source;
    end target : Foo :>> BinaryLinkObject::target;
  }
}
