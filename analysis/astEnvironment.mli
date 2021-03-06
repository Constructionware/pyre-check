(* Copyright (c) 2019-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree. *)

open Ast
open SharedMemoryKeys

module ResolvedReference : sig
  type export =
    | FromModuleGetattr
    | Exported of Module.Export.t
  [@@deriving sexp, compare, hash]

  type t =
    | Module of Reference.t
    | ModuleAttribute of {
        from: Reference.t;
        name: Identifier.t;
        export: export;
        remaining: Identifier.t list;
      }
    | PlaceholderStub of {
        stub_module: Reference.t;
        remaining: Identifier.t list;
      }
  [@@deriving sexp, compare, hash]
end

type t

module ReadOnly : sig
  type t

  val create
    :  ?get_source:(Reference.t -> Source.t option) ->
    ?get_source_path:(Reference.t -> SourcePath.t option) ->
    ?is_module:(Reference.t -> bool) ->
    ?all_explicit_modules:(unit -> Reference.t list) ->
    ?get_module_metadata:(?dependency:DependencyKey.registered -> Reference.t -> Module.t option) ->
    ?module_exists:(?dependency:DependencyKey.registered -> Reference.t -> bool) ->
    unit ->
    t

  val get_source : t -> Reference.t -> Source.t option

  val get_source_path : t -> Reference.t -> SourcePath.t option

  val is_module : t -> Reference.t -> bool

  val get_relative : t -> Reference.t -> string option

  val get_real_path
    :  configuration:Configuration.Analysis.t ->
    t ->
    Reference.t ->
    Pyre.Path.t option

  val get_real_path_relative
    :  configuration:Configuration.Analysis.t ->
    t ->
    Reference.t ->
    string option

  val all_explicit_modules : t -> Reference.t list

  val get_module_metadata
    :  t ->
    ?dependency:DependencyKey.registered ->
    Reference.t ->
    Module.t option

  val module_exists : t -> ?dependency:DependencyKey.registered -> Reference.t -> bool

  val legacy_resolve_exports
    :  t ->
    ?dependency:DependencyKey.registered ->
    Reference.t ->
    Reference.t

  val resolve_exports
    :  t ->
    ?dependency:DependencyKey.registered ->
    ?from:Reference.t ->
    Reference.t ->
    ResolvedReference.t option

  val resolve_decorator_if_matches
    :  t ->
    ?dependency:SharedMemoryKeys.DependencyKey.registered ->
    Ast.Statement.Decorator.t ->
    target:string ->
    Ast.Statement.Decorator.t option

  val get_decorator
    :  t ->
    ?dependency:SharedMemoryKeys.DependencyKey.registered ->
    ClassSummary.t Node.t ->
    decorator:string ->
    Ast.Statement.Decorator.t list
end

(* Store the environment to saved-state *)
val store : t -> unit

(* Load the environment from saved-state. Taking a `ModuleTracker` parameter just to signal that
   loading an `AstEnvironment` must be done after loading a `ModuleTracker` *)
val load : ModuleTracker.t -> t

val shared_memory_hash_to_key_map : Reference.t list -> string Core.String.Map.t

val serialize_decoded : Memory.decodable -> (string * string * string option) option

val decoded_equal : Memory.decodable -> Memory.decodable -> bool option

val create : ModuleTracker.t -> t

module UpdateResult : sig
  type t

  val triggered_dependencies : t -> DependencyKey.RegisteredSet.t

  val reparsed : t -> Reference.t list

  val syntax_errors : t -> SourcePath.t list

  val system_errors : t -> SourcePath.t list

  val create_for_testing : unit -> t
end

type trigger =
  | Update of ModuleTracker.IncrementalUpdate.t list
  | ColdStart

val update
  :  configuration:Configuration.Analysis.t ->
  scheduler:Scheduler.t ->
  t ->
  trigger ->
  UpdateResult.t

val read_only : t -> ReadOnly.t
